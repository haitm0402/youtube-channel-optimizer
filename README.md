# YouTube Channel Optimizer

Công cụ Python hỗ trợ tạo và tối ưu kênh YouTube Music từ thông tin kênh đối thủ.
**Trạng thái: PHASE 2 — AI Service + Structured Prompt System, chạy offline với mock.**
PHASE 1 đã có models, settings và JSON export; PHASE 2 mở rộng trên bộ khung đó.
Chưa triển khai GUI, scraping YouTube, sinh ảnh, API AI thật, upload hay browser automation.

## Workflow và kiến trúc PHASE 2

```text
CompetitorInput (URL + avatar reference + description + optional target)
  → CompetitorAnalysisService → CompetitorAnalysis
  → ChannelNameService → ChannelNameResult (12 tên + best_recommendation)
  → Người dùng chọn một tên trong danh sách
  → ChannelPackageService → ChannelPackage
  → ChannelProfile → exports/channel_profile.json
```

Mỗi service dùng cùng quy trình:

```text
UTF-8 Markdown file → PromptLoader → PromptRenderer
→ TextGenerator.generate(prompt=...)
→ strict JSON parse → strict model validation → typed result
```

- `core.contracts.TextGenerator` là `Protocol` hiện có, không phụ thuộc SDK.
  Services nhận provider qua constructor; provider chỉ trả text, không quyết định
  validation. Provider khác có thể thay thế bằng cùng method `generate(*, prompt) -> str`.
- `core.ai_services` chứa orchestration. `services` chứa adapter và factory tại điểm
  composition. `create_text_generator` hiện chỉ hỗ trợ `mock`; provider chưa triển khai
  gây `ProviderError`, không tự fallback hoặc gọi API thật.
- `core.responses.parse_response` yêu cầu một JSON object, không chấp nhận prose,
  Markdown fences, trailing content, duplicate keys, NaN hoặc Infinity. JSON sai cú pháp
  gây `MalformedResponseError`; schema sai gây `ResponseValidationError`.
  Không repair, thêm trường thiếu, retry hay âm thầm nhận output sai.
- Models dùng dataclass và validation của thư viện chuẩn. Các factory `from_ai_dict`
  kiểm tra đúng tập keys, kiểu dữ liệu và quy tắc nghiệp vụ, kể cả nested objects.

## Models và tương thích

- `CompetitorAnalysis` có summary, positioning, reference_artist, music_niche,
  genre, subgenre, target_market, language, target_audience, visual_identity,
  tone_of_voice, seo_topics, branding_characteristics, strengths và opportunities.
  AI phải trả mọi key; `reference_artist` được phép là `null` khi chưa biết.
  Các trường text khác và các list phải không rỗng.
- `NameCandidate` có name, category (`positioning`, `brand`, `memorable`), short_reason
  và score hữu hạn 0–10. `ChannelNameResult` bắt buộc đúng **12 tên**, **4 mỗi category**,
  tên không trùng sau khi trim/casefold, và best_recommendation khớp chính xác một tên.
  Package generation chỉ nhận tên đã được người dùng chọn trong kết quả này.
- `ChannelPackage` có channel_positioning, đúng **4** `AvatarConcept`, một `BannerConcept`,
  channel_description, channel_keywords, video_core_keywords, video_tags, hashtags,
  title_templates, thumbnail_visual_guide và slogan.
  Avatar có concept, composition, colors (list), lighting, background, main_subject,
  image_prompt. Banner có concept, layout, background, typography_direction,
  main_visual và image_prompt. Đây là mô tả/prompt văn bản, không phải ảnh đã sinh.
- Giữ constructor và alias PHASE 1: `audience` ↔ `target_audience`, `rationale` ↔
  `short_reason`, `prompt` ↔ `image_prompt`. Alias mâu thuẫn gây lỗi. Package giữ các
  trường cũ `positioning`, `description`, `banner_concept`, `banner_prompt`; các tên
  canonical mới có qua properties và `from_ai_dict`/`to_ai_dict`.
- Model legacy được phép thiếu enrichment mới để đọc dữ liệu PHASE 1; **AI factories
  luôn yêu cầu schema PHASE 2 đầy đủ**. Services không cho analysis legacy thiếu dữ
  liệu đi tiếp như analysis hoàn chỉnh. Có thể dùng `ChannelPackage.from_ai_dict`
  để khởi tạo package bằng schema canonical mới.
- Export `ChannelProfile` giữ `schema_version = 1`, tên trường PHASE 1 và bổ sung
  enrichment mới; JSON PHASE 1 cũ vẫn đọc được bởi code hiện tại. Code PHASE 1 cũ
  không được đảm bảo đọc export đã mở rộng. `to_ai_dict` là shape canonical cho AI;
  `ChannelProfile.to_dict` là shape persistence có aliases để tương thích.
- Dataclass frozen chỉ ngăn gán lại field, không đóng băng list. Service kiểm tra lại
  analysis/name collections trước khi dùng để tránh bỏ qua quy tắc qua list mutation.

Validation kiểm tra cấu trúc và quy tắc, không chứng minh chất lượng nội dung, tính
khả dụng tên kênh, SEO hiệu quả hoặc dữ liệu thực tế của đối thủ. URL chỉ được kiểm
tra hình thức/hostname YouTube; avatar reference chưa được tải hoặc phân tích ảnh.

## Cấu trúc project

```text
app.py                         # Kiểm tra config và CLI mock demo với bước chọn tên
core/
  contracts.py                 # TextGenerator / CompetitorSource ports
  errors.py                    # Application errors
  prompts.py                   # PromptLoader / PromptRenderer
  responses.py                 # Strict JSON → typed model
  ai_services.py               # Ba application services
models/
  channel.py                   # Models legacy + enriched models + strict AI factories
  validation.py                # Validation primitives
config/
  default.toml                 # Cấu hình mặc định không chứa secret
  settings.py                  # TOML + environment overrides
prompts/
  README.md
  analyze_competitor.md
  generate_names.md
  generate_package.md
services/
  providers.py                 # Composition factory
  mock.py                      # MockTextGenerator
  mock_data/
    analysis.json
    names.json
    package.json
utils/
  json_io.py                   # ChannelProfile UTF-8 read/write
exports/
  .gitkeep                     # Export thực tế được Git bỏ qua
tests/
  __init__.py
  helpers.py
  test_models.py               # PHASE 1 regression checks
  test_config.py
  test_ai_models.py
  test_ai_services.py
  test_prompts.py
  test_settings_env.py
.env.example
.gitignore
requirements.txt
README.md
```

Các package `core`, `models`, `config`, `services`, `utils` có `__init__.py`.

## Prompt system

Prompt được lưu ngoài source Python dưới dạng UTF-8 Markdown. Biến dùng `${name}`
hoặc `$name`; literal dollar dùng `$$`. JSON braces và các slot title như `{artist}`
giữ nguyên. Renderer thay thế một lần, không diễn giải `${...}` trong nội dung input.
File thiếu, file rỗng, sai UTF-8, đường dẫn thoát prompt directory, syntax không hợp lệ
hoặc thiếu biến đều gây `PromptError` với thông báo cụ thể.

Thêm template mới vào prompt directory rồi gọi `loader.load("new_prompt.md")` và
`renderer.render(template, variables)`; không cần sửa loader. Task mock mới cần fixture
và đăng ký trong mock adapter. Ba template hiện tại mô tả schema JSON; Python vẫn là
nơi bắt buộc xác thực output. Prompt không chứng minh đã truy cập URL hay avatar.

## Cài đặt và chạy

Yêu cầu **Python 3.11+** (`tomllib` và `string.Template` introspection).
Cả hai phase chỉ dùng thư viện chuẩn; không cần API key, SDK hoặc Internet.

Windows PowerShell, từ thư mục repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py --mock-demo
.\.venv\Scripts\python.exe app.py --mock-demo --select-name "Mây Âm Nhạc"
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python app.py --mock-demo
.venv/bin/python app.py --mock-demo --select-name "Mây Âm Nhạc"
```

`--mock-demo` hiển thị analysis, 12 tên và recommendation; **chưa tạo package** cho tới
khi truyền `--select-name` khớp một suggestion. Chọn tên khác recommendation cũng được.
Profile xuất vào `exports/channel_profile.json`; chạy lại với tên đã chọn sẽ ghi đè
file export đó. CLI dùng example input và fixture minh họa, không lấy dữ liệu từ YouTube.
`--mock-demo` luôn chọn mock kể cả settings đang trỏ provider khác.

Mock dùng fixture cố định tiếng Việt, không mô phỏng việc suy luận theo mọi artist/
market/language. Description của package phản ánh tên được chọn; các dữ liệu còn lại
cố định để test hợp đồng. Task được định tuyến bằng dòng đầu template, không bằng nội
dung đối thủ. Có thể sử dụng các service trực tiếp với input thực, nhưng mock vẫn trả
fixture, không đưa ra phân tích thật.

## Cấu hình và secrets

Đường dẫn dùng `pathlib`; UTF-8 JSON dùng `ensure_ascii=False`. Path trong TOML tính
theo thư mục file config, không theo cwd; defaults tính theo vị trí source. Windows
được hỗ trợ qua API chuẩn và hướng dẫn trên; chưa chạy xác minh trên Windows thực tế.

Có thể tạo `config/local.toml` đã được Git bỏ qua, rồi chạy
`python app.py --config config/local.toml`. Custom config không merge với `default.toml`;
keys bỏ trống dùng defaults của `Settings`. Keys TOML: `project_name`, `ai_provider`,
`ai_model`, `prompts_dir`, `exports_dir`. Default provider vẫn là `unconfigured` để
không kích hoạt provider ngoài ý muốn.

Environment overrides có precedence cao hơn TOML:

| Variable | Mục đích |
| --- | --- |
| `YCO_AI_PROVIDER` | Provider name, hiện chỉ `mock` có adapter |
| `YCO_AI_MODEL` | Model tương lai; mock không sử dụng |
| `YCO_AI_API_KEY` | Credential tương lai; mock không cần/không dùng |

`.env.example` chỉ là ví dụ; ứng dụng **không tự đọc `.env`**. Export variables trong
shell hoặc cấu hình môi trường của máy chạy. Ví dụ:

```powershell
$env:YCO_AI_PROVIDER = "mock"
```

```sh
export YCO_AI_PROVIDER=mock
```

Giá trị environment rỗng bị từ chối. API key chỉ nhận từ environment, không từ TOML,
không xuất trong settings repr, prompt hoặc profile. Không dump settings/env để debug.
`.env` và `.env.*` được Git bỏ qua, ngoại trừ `.env.example`. Không commit key/token thật.

## Kiểm thử và kế hoạch

Lệnh toàn bộ suite: `python -m unittest discover -s tests -v`.
Suite có **61 tests**, gồm PHASE 1 regression, JSON legacy round trip, prompt errors,
Unicode paths/rendering, provider substitution, mock offline pipeline, malformed JSON,
invalid schema, missing/extra fields, score/count/category/recommendation rules,
nested avatar/banner, SEO/slogan/thumbnail, environment settings và CLI selection/export.
Test offline chặn các network entry points tiêu chuẩn và xóa environment trong lúc
chạy pipeline; không cần secret hoặc dịch vụ ngoài.

PHASE 2 dừng tại mock-backed structured pipeline. PHASE 3 và mọi tích hợp provider
thật, nguồn dữ liệu, giao diện hoặc automation sẽ chờ phê duyệt và phạm vi riêng.
