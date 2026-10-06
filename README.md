# YouTube Channel Optimizer

Công cụ Python hỗ trợ tạo và tối ưu kênh YouTube Music từ thông tin kênh đối thủ.
**Trạng thái: PHASE 1 — bộ khung và hợp đồng dữ liệu.** Chưa có GUI, gọi API AI,
scraping YouTube hay chức năng sinh nội dung. Prompt hiện chỉ là placeholder.

## Workflow dự kiến

Competitor URL + avatar + description + target artist/market/language (tùy chọn)
→ phân tích đối thủ → đề xuất tên → người dùng chọn tên → tạo gói kênh đầy đủ
→ xuất `channel_profile.json`.

Gói kênh bao gồm positioning, đúng 4 avatar concepts/prompts, banner concept/prompt,
description, channel keywords, video core keywords, tags, hashtags, title templates
và thumbnail visual guide.

## Cấu trúc

```text
app.py                         # CLI kiểm tra cấu hình, không chạy workflow
core/
  __init__.py
  contracts.py                 # Protocol cho AI và nguồn dữ liệu đối thủ
models/
  __init__.py
  channel.py                   # Input, analysis, name, package, profile
config/
  __init__.py
  default.toml                 # Cấu hình mặc định không chứa secret
  settings.py                  # Loader và kiểm tra cấu hình
prompts/
  README.md
  analyze_competitor.md         # Placeholder
  generate_names.md            # Placeholder
  generate_package.md          # Placeholder
services/
  __init__.py                  # Adapter sẽ được triển khai sau
utils/
  __init__.py
  json_io.py                   # Đọc/ghi ChannelProfile bằng UTF-8
exports/
  .gitkeep                     # File export thực tế được Git bỏ qua
tests/
  test_models.py
  test_config.py
requirements.txt               # Phase 1 chỉ dùng thư viện chuẩn
.gitignore
README.md
```

## Phát triển

Yêu cầu Python **3.11 trở lên** (để dùng `tomllib`). Chạy từ thư mục repository.

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
.venv/bin/python -m unittest discover -s tests -v
```

Không cần API key hoặc kết nối mạng để chạy PHASE 1. `requirements.txt` hiện
không khai báo package bên ngoài. Test dùng `unittest` của Python.

## Quyết định kiến trúc

- Models dùng dataclass với kiểm tra dữ liệu khi khởi tạo. `CompetitorInput` chứa
  URL HTTPS trên hostname YouTube, avatar reference (đường dẫn hoặc URL dưới dạng
  chuỗi, chưa tải/kiểm tra file), mô tả và `TargetAudience` tùy chọn.
  Validation URL chỉ kiểm tra hình thức/hostname, chưa xác minh URL là kênh thật.
- `CompetitorAnalysis` và `NameCandidate` biểu diễn kết quả trung gian;
  `ChannelPackage` yêu cầu đủ các nhóm nội dung và đúng bốn avatar.
- `ChannelProfile` gộp nguồn, phân tích, tên được chọn và package;
  `schema_version = 1` giúp quản lý thay đổi định dạng JSON sau này.
  `to_dict()`/`from_dict()` hỗ trợ round trip. Schema không phải là cơ chế
  đánh giá chất lượng nội dung hoặc xác thực dữ liệu từ AI.
- `core` định nghĩa các port bằng `Protocol`; `services` sẽ cung cấp adapter.
  Không có phụ thuộc OpenAI trong nghiệp vụ. Việc đăng ký/chọn adapter thực tế
  sẽ được triển khai sau; `ai_provider` hiện chỉ là cấu hình.
- Prompt nằm ngoài source Python. Adapter/prompt loader tương lai đọc chúng qua
  `Settings.prompts_dir`; không gửi placeholder cho AI.
- Đường dẫn dùng `pathlib`; đường dẫn trong TOML tính theo thư mục file cấu hình,
  cấu hình mặc định tính theo vị trí source, không theo current working directory.
  JSON ghi rõ UTF-8 và `ensure_ascii=False` để bảo toàn tiếng Việt/Unicode.
- Dataclass frozen ngăn gán lại trường nhưng các list bên trong vẫn có thể thay đổi;
  cần tạo/kiểm tra lại model khi cập nhật dữ liệu, không coi đây là deep immutability.

Có thể tạo `config/local.toml` (đã được Git bỏ qua), rồi chạy:

```sh
python app.py --config config/local.toml
```

File cấu hình tùy chỉnh không merge với `default.toml`: trường bỏ trống dùng default
của `Settings`. Các khóa được hỗ trợ: `project_name`, `ai_provider`, `ai_model`,
`prompts_dir`, `exports_dir`. Không lưu credentials trong TOML hoặc source;
thiết kế secrets cho adapter sẽ được bổ sung khi có provider cụ thể.

## Kế hoạch phát triển

1. **PHASE 1 (hiện tại):** cấu trúc module, models, settings, placeholder prompts,
   UTF-8 JSON helpers và test tự động.
2. **PHASE 2 (chờ phê duyệt):** thống nhất hợp đồng workflow và triển khai orchestration
   với fake adapters; quản lý bước chọn tên và validation kết quả.
3. **Giai đoạn tiếp theo:** prompt thật, adapter AI có thể thay thế và quản lý secrets;
   nguồn dữ liệu YouTube chỉ triển khai khi phạm vi/điều kiện truy cập được xác định.
4. **Sau khi workflow ổn định:** giao diện, lưu trạng thái, UX chọn tên và xuất gói kênh.

Test kiểm tra input không hợp lệ, bốn avatar bắt buộc, phiên bản schema, JSON Unicode,
TOML, đường dẫn độc lập cwd và prompt assets. Windows được hỗ trợ bằng API thư viện
chuẩn và lệnh riêng ở trên; cần chạy CI Windows để xác nhận trên Windows thực tế.
