# Commit giao diện RiceShift lên GitHub

Repo đích: **https://github.com/vuhoaii/agrishift-360**.

Thư mục đang chỉnh sửa `D:\agrishift-360` hiện không có `.git`, còn repo GitHub đã có nhánh `main` và lịch sử. Quy trình dưới đây clone vào **một thư mục mới**, chép phần giao diện/tài liệu rồi commit trên một nhánh riêng.

Chạy các lệnh trong **PowerShell**. Hướng dẫn này để bạn tự thực hiện; việc chuẩn bị README không tự push hoặc deploy.

## 1. Clone vào thư mục mới

~~~powershell
Set-Location D:\
git clone https://github.com/vuhoaii/agrishift-360.git agrishift-360-publish
Set-Location D:\agrishift-360-publish
git switch -c ui/riceshift-field-notebook
~~~

Nếu `D:\agrishift-360-publish` đã tồn tại, chọn tên thư mục mới khác và sửa `$publishRoot` ở bước tiếp theo cho đúng.

## 2. Chép phần giao diện và tài liệu đã chuẩn bị

Giữ nguyên nguồn `D:\agrishift-360`. Đoạn lệnh này chép đúng các file cần cho giao diện Flask và bộ tài liệu vào bản clone:

~~~powershell
$sourceRoot = 'D:\agrishift-360'
$publishRoot = 'D:\agrishift-360-publish'

$files = @(
    'README.md',
    'render.yaml',
    '.python-version',
    'RiceShift\web.py',
    'RiceShift\frontend_i18n.py',
    'RiceShift\presentation_messages.py',
    'RiceShift\requirements-web.txt',
    'RiceShift\test_frontend.py'
)

foreach ($relativePath in $files) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $relativePath) -Destination (Join-Path $publishRoot $relativePath) -Force
}

foreach ($relativeFolder in @('RiceShift\templates', 'RiceShift\static', 'docs')) {
    $targetFolder = Join-Path $publishRoot $relativeFolder
    New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $sourceRoot $relativeFolder) -Force |
        Copy-Item -Destination $targetFolder -Recurse -Force
}

Set-Location $publishRoot
git status --short
git diff --stat
git diff --check
git diff -- RiceShift/web.py
~~~

Các thư mục `RiceShift/services` và `RiceShift/data` không nằm trong danh sách chép; bản clone giữ nguyên Decision Engine, dữ liệu và các file đang có trên GitHub. Các ảnh của README được chép cùng `docs`.

## 3. Chạy kiểm tra trên bản chuẩn bị commit

Có thể dùng Python trong venv hiện có của thư mục nguồn:

~~~powershell
Set-Location D:\agrishift-360-publish\RiceShift
& 'D:\agrishift-360\RiceShift\.venv\Scripts\python.exe' -B -m unittest test_frontend
& 'D:\agrishift-360\RiceShift\.venv\Scripts\python.exe' -B test_scoring_engine.py
Set-Location D:\agrishift-360-publish
~~~

Nếu máy chưa có venv này, tạo venv và cài phụ thuộc theo [README](../README.md#chạy-trên-máy).

## 4. Stage và xem lại nội dung commit

~~~powershell
git add README.md render.yaml .python-version docs RiceShift/web.py RiceShift/frontend_i18n.py RiceShift/presentation_messages.py RiceShift/requirements-web.txt RiceShift/test_frontend.py RiceShift/templates RiceShift/static
git diff --cached --stat
git diff --cached --check
git status --short
git diff --cached --name-only -- RiceShift/services RiceShift/data
~~~

Lệnh cuối không có đầu ra khi Decision Engine và dữ liệu không nằm trong commit. Nội dung chính cần thấy là frontend, bản dịch, test, ảnh và tài liệu deploy.

## 5. Commit, push nhánh và tạo Pull Request

~~~powershell
git commit -m "feat: redesign RiceShift field notebook UI and add deployment docs"
git push -u origin ui/riceshift-field-notebook
~~~

Git có thể mở trình duyệt để đăng nhập tài khoản GitHub có quyền ghi vào repo.

Nếu Git báo thiếu danh tính người commit, cấu hình riêng cho bản clone rồi chạy lại `git commit`:

~~~powershell
git config user.name "Tên hiển thị của bạn"
git config user.email "Email GitHub hoặc email noreply của bạn"
~~~

Sau khi push, mở [trang tạo Pull Request](https://github.com/vuhoaii/agrishift-360/compare/main...ui/riceshift-field-notebook?expand=1), xem lại **Files changed**, rồi tạo PR vào `main`.

Gợi ý mô tả PR:

~~~markdown
## Thay đổi

- Thiết kế lại sáu màn hình Flask theo phong cách sổ tay đồng ruộng.
- Thêm giao diện VI/EN, điều chỉnh cỡ chữ và menu responsive.
- Tách template, CSS, JavaScript và minh họa SVG.
- Thêm README có ảnh thật, hướng dẫn Git và cấu hình Render.

## Kiểm tra

- python -B -m unittest test_frontend
- python -B test_scoring_engine.py
- git diff --cached --check

Decision Engine và dữ liệu được giữ nguyên.
~~~

Chỉ ghi các kiểm tra bạn đã thực sự chạy thành công. Sau khi review và merge PR vào `main`, tiếp tục [deploy lên Render](DEPLOY.md).

## Những lần cập nhật sau

Làm việc trong bản clone `D:\agrishift-360-publish` để Git theo dõi thay đổi. Với mỗi đợt cập nhật, tạo nhánh từ `main` mới nhất, chạy kiểm tra, commit và push nhánh đó. Nếu Render đang để Auto-Deploy Off, chọn Manual Deploy khi muốn đưa phiên bản mới lên web.
