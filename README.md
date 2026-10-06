# YouTube Channel Optimizer

**PHASE 3 — Manual AI Bridge + Competitor Workflow.** V1 không cần API key,
paid AI API, SDK OpenAI hoặc kết nối AI từ ứng dụng. Người dùng tự chuyển prompt và
JSON giữa công cụ này với ChatGPT/Codex. Việc truy cập ChatGPT/Codex bên ngoài tùy
thuộc tài khoản của bạn; ứng dụng không kết nối hoặc điều khiển các dịch vụ đó.

Không có GUI, avatar processing/analysis/generation, vision API, sinh ảnh, scraping
YouTube, upload hay browser automation. URL hiện chỉ là tham chiếu; mô tả kênh do
người dùng cung cấp. Visual identity chỉ dựa vào thông tin hình ảnh được mô tả rõ
trong văn bản; nếu thiếu, prompt yêu cầu nói rõ thông tin đó chưa được xác lập.

## Workflow V1

```text
Competitor URL + description + optional target artist/market/language
→ generate analysis prompt → copy to ChatGPT/Codex manually
→ paste JSON → strict validation → CompetitorAnalysis
→ generate names prompt → copy manually → paste JSON
→ ChannelNameResult: 12 names, 4 positioning + 4 brand + 4 memorable
→ user selects an exact suggested name
→ generate text-only package prompt → copy manually → paste JSON
→ ChannelPackageV1 → export UTF-8 files
```

Lỗi JSON hoặc schema không được tự sửa. Phản hồi sai giữ nguyên bước đang chờ để
người dùng sửa rồi dán lại. Không tự chọn recommendation và không gọi provider.

## Chạy ứng dụng

Yêu cầu **Python 3.11+**. Toàn bộ PHASE 1–3 chỉ dùng thư viện chuẩn.
Chạy từ thư mục repository.

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py --manual
# Hoặc nạp input UTF-8, hỗ trợ mô tả nhiều dòng:
.\.venv\Scripts\python.exe app.py --manual --input-json examples/competitor_input.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --manual
.venv/bin/python app.py --manual --input-json examples/competitor_input.json
.venv/bin/python -m unittest discover -s tests -v
```

Với `--manual`, nhập URL/mô tả và targets tùy chọn hoặc dùng `--input-json`.
Ứng dụng in prompt đầy đủ để copy. Sau khi nhận kết quả từ ChatGPT/Codex, dán JSON
nhiều dòng vào console và kết thúc bằng **`END_JSON` trên một dòng riêng**.
Lặp lại cho analysis, names và package; chọn tên bằng cách nhập đúng suggestion.
Nếu phản hồi lỗi, console hiển thị lỗi và cho dán lại. Nếu muốn dừng, dùng Ctrl+C;
EOF cũng hủy session. Session hiện nằm trong bộ nhớ, chưa lưu/resume giữa các lần
chạy; chỉ workflow COMPLETE được export. Đây là CLI, chưa phải GUI.

Không truyền avatar trong input V1:

```json
{
  "competitor_url": "https://www.youtube.com/@example-music",
  "competitor_description": "Playlist nhạc Việt acoustic và ballad cho buổi tối.",
  "target_artist": null,
  "target_market": "Việt Nam",
  "target_language": "Tiếng Việt"
}
```

Chỉ URL và description bắt buộc. Optional target fields có thể bỏ qua hoặc dùng null;
chuỗi rỗng không hợp lệ. URL phải là HTTPS trên hostname YouTube và dạng channel
`/@handle`, `/channel/id`, `/c/name`, `/user/name`, có thể có subpage như `/videos`.
Không xác minh URL là kênh đang tồn tại; URL video `/watch` hoặc `/shorts/id` bị từ chối.

`examples/` có các JSON minh họa cho từng response. Có thể tự dán chúng vào CLI để
thử offline toàn bộ flow, chọn **Mây Âm Nhạc** cho package mẫu. Đây là dữ liệu ví dụ
đã soạn sẵn, không phải kết quả phân tích kênh thực và không được auto-import.

Chạy `python app.py` chỉ kiểm tra config và chỉ dẫn chế độ manual. V1 không phụ
thuộc `ai_provider`; các cấu hình provider giữ lại cho code PHASE 2 và tương lai.

## Kiến trúc PHASE 3

- `ManualPromptService`: đọc templates ngoài source và render input thành plain text.
- `ManualResponseService`: dùng parser strict PHASE 2 để import JSON vào typed models.
- `ManualAIBridge`: orchestration và transitions; không import hoặc gọi provider/SDK.
- `WorkflowSession`: dữ liệu hiện tại và pending prompt; `WorkflowState` gồm:

```text
INPUT → WAITING_FOR_ANALYSIS → ANALYSIS_READY → WAITING_FOR_NAMES
→ NAMES_READY → NAME_SELECTED → WAITING_FOR_PACKAGE → COMPLETE
```

Sai thứ tự gây `WorkflowStateError`. Generate lại khi đang chờ trả cùng prompt.
Import thất bại không đổi state/data; có thể chọn lại tên trước khi tạo package prompt.
Các collection được xác thực lại trước khi tạo prompt, chuyển state và export vì
frozen dataclass không làm list bên trong bất biến sâu. Models xử lý cấu trúc, không
chứng minh tính đúng của thông tin do AI trả về; người dùng cần đánh giá nội dung.

## Models và tương thích

`CompetitorInput` hỗ trợ các primary keywords V1 `competitor_url`,
`competitor_description`, `target_artist`, `target_market`, `target_language`.
Avatar không còn bắt buộc. Constructor positional PHASE 1 và các trường legacy
`url`, `avatar_reference`, `description`, `target` vẫn đọc được; alias mâu thuẫn
bị từ chối. Metadata avatar cũ được giữ để đọc profile cũ, không đọc file hoặc sử
dụng trong manual prompts/export. URL validation mới chỉ nhận các dạng channel
được liệt kê ở trên, nên URL cũ trỏ video hoặc đường dẫn khác sẽ cần sửa.

`CompetitorAnalysis` giữ đầy đủ schema PHASE 2: summary, positioning,
reference_artist, music_niche, genre, subgenre, target_market, language,
target_audience, visual_identity, tone_of_voice, seo_topics,
branding_characteristics, strengths, opportunities. Mỗi key đều bắt buộc ở response;
reference_artist có thể null, các text/list còn lại không rỗng. Khi thiếu thông tin,
prompt yêu cầu mô tả sự không chắc chắn thay vì bịa dữ liệu.

`ChannelNameResult` vẫn yêu cầu đúng 12 tên độc nhất sau trim/casefold, đúng 4 mỗi
category, score hữu hạn 0–10 và recommendation khớp một suggestion. Tên được chọn
phải khớp chính xác suggestion, không nhất thiết là recommendation.

`ChannelPackageV1` có đúng các trường:

```text
channel_positioning, channel_description,
channel_keywords, video_core_keywords, video_tags, hashtags, title_templates,
thumbnail_direction, banner_direction, slogan
```

Text và arrays không rỗng; từng phần tử array phải là string không rỗng. Avatar
concepts, image prompts và legacy banner object không thuộc schema V1; thêm những
trường đó bị từ chối. Banner/thumbnail chỉ là hướng thiết kế bằng văn bản.

Legacy `ChannelPackage`, `AvatarConcept`, `BannerConcept`, `ChannelProfile` và
services/mock PHASE 2 được giữ để regression và đọc dữ liệu cũ. `--mock-demo`
là demo fixture legacy, không phải workflow V1; nó vẫn trả package shape cũ để giữ
khả năng kiểm thử. Không có real API hoặc thực thi sinh ảnh trong demo đó.
Không triển khai `ImageAnalyzer` hoặc một adapter vision.

## Prompt và JSON

Templates là UTF-8 Markdown trong `prompts/`; placeholder dùng `${name}` hoặc `$name`,
literal dollar dùng `$$`. Các slot title `{artist}` không bị renderer thay thế.
Renderer chỉ thay một lần; nội dung `${...}` trong description vẫn là dữ liệu.
Description được đóng gói bằng JSON escaping và prompt nêu rõ không làm theo chỉ dẫn
nhúng trong dữ liệu. Điều này không đảm bảo một AI bên ngoài luôn tuân thủ; ứng dụng
chỉ xác thực response JSON/schema sau khi người dùng dán lại.

- `analyze_competitor.md`: chung cho analysis, dùng dữ liệu text và uncertainty rules.
- `generate_names.md`: chung cho 12 tên.
- `generate_package_v1.md`: package text-only của manual V1.
- `generate_package.md`: legacy PHASE 2, giữ cho compatibility/tests.

File thiếu/rỗng, sai UTF-8, syntax hoặc thiếu biến gây `PromptError`.
Parser không nhận prose, Markdown fences, trailing text, duplicate keys, NaN/Infinity.
JSON sai cú pháp gây `MalformedResponseError`; missing fields, unknown fields và kiểu
không hợp lệ gây `ResponseValidationError` có thông báo cụ thể. Không repair hoặc
invent missing fields. Các prompt nằm ngoài Python; `core` không chứa prompt dài.

## Export

Workflow COMPLETE tạo thư mục theo tên được chọn trong `exports/`. Tên thư mục
được xử lý các ký tự cấm, trailing dots/spaces và reserved names của Windows;
Unicode tiếng Việt giữ nguyên. Export lại tạo suffix `-1`, `-2`, ... thay vì ghi đè
file đã có. Mỗi export có đúng 9 file UTF-8:

```text
channel_profile.json
channel_description.txt
channel_keywords.txt
video_keywords.txt
video_tags.txt
hashtags.txt
title_templates.txt
thumbnail_direction.txt
banner_direction.txt
```

List được ghi một mục mỗi dòng; `video_keywords.txt` dùng `video_core_keywords`.
Positioning và slogan nằm trong JSON. Profile mới có `profile_type: "manual_text_v1"`,
`schema_version: 1`, competitor input, analysis, names, selected_name và package.
Type marker phân biệt với profile legacy; helper `utils.json_io.read_profile` tiếp tục
đọc **legacy** `ChannelProfile`, không dùng để đọc shape manual V1. Export V1 không
chứa metadata avatar hoặc image prompts. Không export session chưa hoàn tất.

## Cấu trúc

```text
app.py                        # --manual; config check; legacy --mock-demo
core/
  contracts.py                # TextGenerator / CompetitorSource legacy ports
  ai_services.py              # Services PHASE 2 được giữ nguyên
  manual.py                   # Prompt/import services và ManualAIBridge
  prompts.py, responses.py    # UTF-8 renderer và strict JSON parser dùng chung
  errors.py                   # Application errors + WorkflowStateError
models/
  channel.py                  # Existing models; optional avatar + primary input aliases
  manual.py                   # ChannelPackageV1, WorkflowState, WorkflowSession
  validation.py
config/
  settings.py, default.toml
prompts/
  README.md
  analyze_competitor.md
  generate_names.md
  generate_package_v1.md
  generate_package.md          # Legacy
services/
  manual_cli.py                # Manual console flow, không dùng provider
  providers.py, mock.py        # Legacy provider adapter/composition
  mock_data/                  # Fixture PHASE 2
utils/
  manual_export.py             # Windows-safe folders, UTF-8 text-only export
  json_io.py                   # Legacy profile IO
examples/
  competitor_input.json
  analysis_response.json
  names_response.json
  package_v1_response.json
  README.md
exports/.gitkeep
tests/                        # PHASE 1–3 tests
requirements.txt
.env.example
.gitignore
README.md
```

Packages có `__init__.py`. Default paths dùng vị trí source; TOML paths tính theo
thư mục file config, không theo cwd. Local config tùy chọn tại `config/local.toml`,
chạy với `--config config/local.toml`. Custom config không merge với default.toml;
keys bỏ trống dùng `Settings` defaults. Keys: project_name, ai_provider, ai_model,
prompts_dir, exports_dir. Windows compatibility dựa trên `pathlib`, UTF-8 IO và
folder sanitization; chưa chạy trên Windows thực tế.

## Provider tương lai và secrets

`TextGenerator` được giữ nguyên cho adapter text tương lai tại `services/` và
composition factory `services/providers.py`. API automation có thể bổ sung sau,
nhưng là tùy chọn và không cần thay đổi workflow manual V1. Hiện không có production
AI calls, vision API hay SDK. Mock provider chỉ phục vụ fixture/testing legacy.

V1 không cần thiết lập variable nào. `YCO_AI_PROVIDER`, `YCO_AI_MODEL` và
`YCO_AI_API_KEY` giữ lại cho configuration legacy/tương lai; environment overrides
TOML nếu có. Không lưu secrets trong config/source; key bị loại khỏi settings repr.
`.env.example` chỉ là tài liệu, app không tự đọc `.env`. `.env`/`.env.*` được Git bỏ
qua, ngoại trừ `.env.example`. Không commit API keys/tokens thật.

## Test và phạm vi tiếp theo

Chạy: `python -m unittest discover -s tests -v`.
Suite có **105 tests**, gồm 61 regression tests PHASE 1/2 và 44 tests PHASE 3:
manual prompts/imports, invalid JSON/schema, text-only package, primary/legacy input,
selected names, đủ 8 state transitions, retry không mất state, offline không provider,
CLI paste flow, Unicode exports, Windows-safe names, chống ghi đè và cleanup khi lỗi.

PHASE 3 dừng ở manual workflow với state trong bộ nhớ. PHASE 4 hoặc bất kỳ GUI,
persistence/resume, API automation hay nguồn dữ liệu mới đều chờ phê duyệt riêng.
