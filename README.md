# YouTube Channel Optimizer

**PHASE 5 — Windows Desktop GUI + Persistent Channel Library.** V1 không cần API key,
paid AI API, SDK OpenAI hoặc kết nối AI từ ứng dụng. Người dùng tự chuyển prompt và
JSON giữa công cụ này với ChatGPT/Codex. Việc truy cập ChatGPT/Codex bên ngoài tùy
thuộc tài khoản của bạn; ứng dụng không kết nối hoặc điều khiển các dịch vụ đó.

GUI dùng Tkinter/ttk. Không có avatar processing/analysis/generation, vision API, sinh ảnh, scraping
YouTube, upload hay browser automation. URL hiện chỉ là tham chiếu; mô tả kênh do
người dùng cung cấp. Visual identity chỉ dựa vào thông tin hình ảnh được mô tả rõ
trong văn bản; nếu thiếu, prompt yêu cầu nói rõ thông tin đó chưa được xác lập.

## Desktop GUI

```powershell
.\.venv\Scripts\python.exe app.py --gui
# Hoặc: py -3 app.py --gui
```

Windows Python installer cần chọn **Tcl/Tk and IDLE**. Linux cần gói Tcl/Tk của
hệ điều hành và một display server; CLI/controller tests chạy không cần display.
Không cần CustomTkinter hay clipboard dependency: ttk đáp ứng giao diện V1 với
thư viện chuẩn và giảm yêu cầu cài đặt Windows.

MY CHANNELS → NEW CHANNEL → tạo project → COPY PROMPT → tự chuyển sang ChatGPT →
dán JSON và VALIDATE & CONTINUE. Chọn một trong 12 tên rồi hoàn tất package/export.
Active là project chưa hoàn tất; Completed là project COMPLETE chưa archive.
Archived chỉ cho đọc; package đã hoàn tất vẫn copy/export được. Archive cần xác nhận.

`GUIController` dùng `ManualAIBridge`, `ChannelLibrary`, `JsonSessionStore` và
exporter hiện có; widget không chứa validation hoặc session model riêng. Prompt
vẫn nằm ngoài Python. Một worker tuần tự thực hiện local I/O; Tk và clipboard
chỉ chạy trên main thread. Không có network operation trong GUI.

Mở project khôi phục trực tiếp từ persisted state. Chỉ các bước INPUT,
ANALYSIS_READY và NAME_SELECTED chưa có pending prompt mới chuẩn bị prompt tiếp
theo. REGENERATE DISPLAY chỉ đọc lại chuỗi pending prompt đã lưu. Lỗi JSON giữ
nguyên textbox/state. JSON chưa validate và đường dẫn export đang hiển thị không
được lưu; dữ liệu đã validate được autosave. Nếu một thao tác lưu thành công nhưng
chuẩn bị prompt tiếp theo thất bại, RELOAD PROJECT tiếp tục từ state đã lưu.

Tất cả Settings paths được dùng lại; `--config` cũng áp dụng cho GUI. Hướng dẫn
kiểm tra Windows: [docs/WINDOWS_GUI_TEST.md](docs/WINDOWS_GUI_TEST.md).

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

Yêu cầu **Python 3.11+**. Toàn bộ PHASE 1–5 chỉ dùng thư viện chuẩn; GUI cần Tcl/Tk.
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
EOF cũng dừng lần chạy hiện tại. Session và mọi transition thành công đã được lưu
local, không bị xóa khi đóng console; dùng `--manual --resume SESSION_ID` để tiếp tục.
JSON đang dán dở chưa import thành công không được lưu. Chỉ COMPLETE được export.

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

## Manual bridge và persistence PHASE 4

- `ManualPromptService`: đọc templates ngoài source và render input thành plain text.
- `ManualResponseService`: dùng parser strict PHASE 2 để import JSON vào typed models.
- `ManualAIBridge`: orchestration và transitions; không import hoặc gọi provider/SDK.
- `WorkflowSession`: dữ liệu hiện tại, pending prompt, UUID, display name, timestamps,
  revision và archive flag; `WorkflowState` gồm:

```text
INPUT → WAITING_FOR_ANALYSIS → ANALYSIS_READY → WAITING_FOR_NAMES
→ NAMES_READY → NAME_SELECTED → WAITING_FOR_PACKAGE → COMPLETE
```

Sai thứ tự gây `WorkflowStateError`. Generate lại khi đang chờ trả cùng prompt.
Import thất bại không đổi state/data; có thể chọn lại tên trước khi tạo package prompt.
Các collection được xác thực lại trước khi tạo prompt, chuyển state và export vì
frozen dataclass không làm list bên trong bất biến sâu. Models xử lý cấu trúc, không
chứng minh tính đúng của thông tin do AI trả về; người dùng cần đánh giá nội dung.

## Session local, resume và thư viện kênh

CLI mặc định lưu session tự động khi dùng `--manual`. Ví dụ từ thư mục repository:

```sh
python app.py --manual --new --input-json examples/competitor_input.json --display-name "Dự án nhạc Việt"
python app.py --sessions
python app.py --manual --resume SESSION_ID
python app.py --view-session SESSION_ID
python app.py --export-session SESSION_ID
python app.py --archive SESSION_ID
python app.py --sessions --archived
```

Thay `SESSION_ID` bằng UUID được in khi tạo session hoặc tìm trong `--sessions`.
`--manual` không có `--resume` vẫn tạo session mới để giữ cách dùng PHASE 3.
`--resume` dùng input và label đã lưu, không kết hợp với `--input-json`/`--display-name`.
`--view-session` chỉ đọc JSON typed hiện có. `--export-session` yêu cầu COMPLETE và
cho phép export cả session đã archive. Export lại luôn tạo thư mục mới có suffix,
không ghi đè export trước. Resume COMPLETE cũng export lại từ package đã lưu, không
hỏi AI hoặc dán lại response.

| State được mở lại | Hành vi |
| --- | --- |
| INPUT | Tạo analysis prompt, lưu trước khi hiển thị |
| WAITING_FOR_ANALYSIS | Hiển thị đúng pending analysis prompt đã lưu |
| ANALYSIS_READY | Dùng analysis cũ để tạo names prompt |
| WAITING_FOR_NAMES | Hiển thị đúng pending names prompt |
| NAMES_READY | Hiển thị 12 tên đã có để người dùng chọn |
| NAME_SELECTED | Dùng tên đã chọn và analysis cũ để tạo package prompt |
| WAITING_FOR_PACKAGE | Hiển thị đúng pending package prompt |
| COMPLETE | Xem hoặc export lại package hiện có |

Không regenerate analysis/names/package đã có. Những prompt đang chờ được lưu
nguyên văn, kể cả nếu template trên đĩa đã thay đổi. Mỗi bước mới chỉ được commit
sau khi validation và save thành công. JSON sai, save lỗi hoặc conflict không làm
state trong bộ nhớ tiến lên và không thay file session đã lưu.

UUID tạo một lần cho project, độc lập với tên kênh được chọn sau này. Display name
là label riêng (mặc định URL), được giữ nguyên khi chọn tên. Timestamps lưu ISO 8601
UTC; created_at không đổi, updated_at thay theo transition/archive. Mỗi lần lưu có
revision để phát hiện bản đọc cũ. Session schema_version hiện là **1**.

Dữ liệu mặc định:

```text
data/
  .gitkeep
  sessions/
    UUID.json                   # Một session đầy đủ, kể cả COMPLETE/archive
    UUID.lock                   # Lock sidecar local; không phải bản sao session
```

JSON lưu metadata, competitor input, state, analysis, names, selected_name, package
và pending prompt nếu đang chờ. Serialization chỉ ghi fields của session, không ghi
settings hoặc API keys. Shape competitor lưu các field legacy để đọc lại input
PHASE 1/2 khi cần; metadata avatar nếu có chỉ được giữ nguyên, không xử lý ảnh và
không đưa vào manual prompt/export. Session JSON khác shape `channel_profile.json`;
không coi export cũ là session để resume.

`data_dir` có thể đặt trong TOML, tương đối theo thư mục config hoặc dùng path tuyệt
đối. Ví dụ file `config/local.toml`:

```toml
data_dir = "../data"
exports_dir = "../exports"
```

Runtime `data/*` được Git bỏ qua, chỉ `data/.gitkeep` được giữ. Nếu đặt data_dir ở
nơi khác, chọn thư mục local ngoài tracked source. Dữ liệu lưu local, không có sync,
Drive hoặc database. Back up thư mục data nếu cần chuyển thư viện sang máy khác.

`core.contracts.SessionStore` tách nghiệp vụ khỏi filesystem. `JsonSessionStore`
ở `services/json_sessions.py` ghi file tạm UTF-8 trong cùng thư mục, flush + fsync,
đóng handle rồi `os.replace`. Dùng lock từng UUID (`msvcrt` trên Windows, `fcntl`
trên POSIX) và compare-and-save revision để ngăn process cũ ghi đè bản mới. Lock
file được giữ để tránh race khi xóa/tạo lại lock; OS nhả lock khi process đóng.
Một process đang giữ lock hoặc revision conflict gây lỗi rõ ràng: reload session
trước khi tiếp tục. Không tuyên bố bảo vệ khỏi mọi sự cố phần cứng/filesystem.
Windows API đã được thiết kế riêng; chưa chạy suite trên Windows thực tế.

`ChannelLibrary` dựng summaries trực tiếp từ session records, không lưu index chứa
bản sao toàn bộ data. `--sessions` chỉ active; `--sessions --archived` chỉ archived.
Summary gồm UUID, display name, competitor URL, reference artist nếu đã biết,
market/language, selected name, state/status và timestamps. Record corrupt hoặc
schema version tương lai gây lỗi với session ID; không âm thầm sửa hoặc bỏ qua.

Archive là flag trong cùng record, không xóa vật lý, không đổi state/pending results.
Archive lặp lại không tạo update mới. Archived sessions read-only: có thể view/export
COMPLETE nhưng không resume workflow; unarchive chưa nằm trong CLI V1.

Core `ManualAIBridge(..., store=store)` lưu INPUT khi tạo và autosave từng transition;
`ManualAIBridge.load_session(id, prompts, store)` hydrate đúng state. Giữ tùy chọn
`store=None` cho in-memory tests/caller cũ; CLI luôn truyền local store. GUI
dùng cùng bridge, `ChannelLibrary` và exporter; chỉ thay lớp nhập/xuất console,
không cần đổi business logic hoặc thêm API provider.

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
app.py                        # --gui, --manual; config check; legacy --mock-demo
core/
  contracts.py                # SessionStore và legacy text/source ports
  ai_services.py              # Services PHASE 2 được giữ nguyên
  manual.py                   # Prompt/import, autosave và resume qua SessionStore
  channel_library.py          # Metadata summaries và archive
  prompts.py, responses.py    # UTF-8 renderer và strict JSON parser dùng chung
  errors.py                   # Application errors + WorkflowStateError
models/
  channel.py                  # Existing models; optional avatar + primary input aliases
  manual.py                   # Text package, state và strict session serialization
  session_metadata.py        # UUID và UTC timestamp validation
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
  manual_cli.py                # Persistent new/resume flow, không dùng provider
  json_sessions.py             # Local atomic JSON store
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
data/.gitkeep                  # Session/lock files runtime được Git bỏ qua
gui/
  controller.py                # State-to-screen mapping; delegates to existing bridge
  main_window.py, app.py        # ttk shell, serialized local I/O worker, lazy launcher
  project_list.py              # Library, filters, archive confirmation
  project_form.py              # Existing CompetitorInput fields
  project_editor.py            # Prompts, JSON, names, package/export screens
  widgets.py, dialogs.py        # Unicode text, clipboard, friendly errors
  platform.py                  # Checked folder opening without shell
docs/WINDOWS_GUI_TEST.md       # Windows manual checklist
tests/                        # PHASE 1–5 regression/controller/Tk smoke tests
requirements.txt
.env.example
.gitignore
README.md
```

Packages có `__init__.py`. Default paths dùng vị trí source; TOML paths tính theo
thư mục file config, không theo cwd. Local config tùy chọn tại `config/local.toml`,
chạy với `--config config/local.toml`. Custom config không merge với default.toml;
keys bỏ trống dùng `Settings` defaults. Keys: project_name, ai_provider, ai_model,
prompts_dir, exports_dir, data_dir. Windows compatibility dựa trên `pathlib`, UTF-8 IO và
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
Suite có **163 tests**, gồm 149 regression tests PHASE 1–4, 13 controller tests
và một functional Tk smoke test (skip khi không có Tcl/Tk hoặc display server).
Các regression checks bao gồm:
manual prompts/imports, invalid JSON/schema, text-only package, primary/legacy input,
selected names, đủ 8 state transitions, retry không mất state, offline không provider,
CLI paste flow, Unicode exports, Windows-safe names, chống ghi đè và cleanup khi lỗi.

PHASE 4 kiểm thử metadata/serialization ở đủ 8 state, autosave, exact prompt resume,
corrupt/incompatible JSON, invalid import giữ nguyên disk/memory, failure của fsync
và replace, stale-writer conflicts, lock behavior, archive/filtering, Unicode paths,
config và CLI restart qua process độc lập. Demo đã dừng ở NAMES_READY rồi mở lại
cùng UUID để hoàn tất; analysis và 12 tên cũ được giữ nguyên.

PHASE 6 chưa bắt đầu. API automation, image features, scraping, sync hoặc database
cần phê duyệt riêng.
