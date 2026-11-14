# Deploy RiceShift lên Render

Render chạy được Flask qua Gunicorn và cung cấp URL HTTPS công khai. Repo đã có `render.yaml` và `.python-version` để chuẩn bị triển khai; các file này chưa tự tạo dịch vụ.

Trước tiên đưa code lên GitHub theo [hướng dẫn commit](GIT_WORKFLOW.md), rồi merge nhánh giao diện vào `main`. Website cần chạy Python; việc chỉ đăng mã lên GitHub chưa tạo website Flask.

## Cách 1 — dùng render.yaml

1. Đăng nhập [Render Dashboard](https://dashboard.render.com/) bằng tài khoản của bạn và kết nối GitHub.
2. Chọn **New → Blueprint**, chọn repo `vuhoaii/agrishift-360`, nhánh `main`.
3. Kiểm tra file `render.yaml` ở thư mục gốc. Cấu hình đề xuất là dịch vụ `riceshift`, gói **Free**, vùng `singapore`.
4. Xem lại cấu hình trước khi bấm nút tạo/triển khai Blueprint. Thao tác này bắt đầu deploy lần đầu.
5. Khi dịch vụ báo **Live**, sao chép URL được hiển thị trong Render.

`autoDeployTrigger: "off"` trong YAML tắt các lần tự deploy sau đó. Muốn đưa commit mới lên website, dùng **Manual Deploy → Deploy latest commit**. [Tham khảo Blueprint](https://render.com/docs/blueprint-spec).

## Cách 2 — nhập cấu hình Web Service thủ công

Chọn **New → Web Service**, kết nối cùng repo và điền:

| Mục | Giá trị |
| --- | --- |
| Repository | `vuhoaii/agrishift-360` |
| Branch | `main` |
| Name | `riceshift`, hoặc tên còn dùng được trong tài khoản của bạn |
| Language / Runtime | `Python 3` |
| Region | `Singapore` |
| Root Directory | **Để trống** — chạy lệnh từ thư mục gốc repo |
| Build Command | `pip install -r RiceShift/requirements-web.txt` |
| Start Command | Lệnh Gunicorn bên dưới |
| Health Check Path | `/health` |
| Instance Type | `Free` |
| Auto-Deploy | `Off` nếu muốn tự chọn từng lần deploy |

**Start Command** — dán nguyên một dòng vào Render:

~~~bash
gunicorn --chdir RiceShift web:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile -
~~~

Lệnh này dành cho môi trường Linux của Render. `$PORT` là cổng Render cấp; Gunicorn nhập `app` từ `RiceShift/web.py`. Vì vậy khối `app.run(debug=True)` dành cho chạy cục bộ không được thực thi.

File `.python-version` ở gốc repo chứa `3.12`. Nếu tài khoản đang có biến `PYTHON_VERSION`, kiểm tra lại vì biến đó được ưu tiên hơn file. [Cấu hình phiên bản Python](https://render.com/docs/python-version).

Sau khi kiểm tra các mục trên, bấm **Create Web Service** để bắt đầu triển khai. [Hướng dẫn Flask của Render](https://render.com/docs/deploy-flask), [cổng và URL của Web Service](https://render.com/docs/web-services).

## Dữ liệu demo

Website đọc payload có sẵn:

~~~text
RiceShift/data/processed/climate_payload_latest.json
~~~

Giữ file này trong Git để bản deploy có dữ liệu. Lệnh build chỉ cài `requirements-web.txt`; không chạy pipeline cập nhật NASA, không sửa dữ liệu và không cần API key.

File được ghi thêm trong môi trường Render Free không phải nơi lưu trữ lâu dài. Bản demo này đọc dữ liệu đã commit và xuất JSON trực tiếp trong response. Nếu sau này cần cập nhật dữ liệu tự động hoặc lưu dữ liệu người dùng, hãy thiết kế phần lưu trữ riêng. [Filesystem của Render Free](https://render.com/docs/free#local-files-lost-on-redeploy).

## Kiểm tra sau khi deploy

Dùng **URL Render thực sự cấp**, thay cho ký hiệu `<ten-dich-vu>` trong các ví dụ:

~~~text
https://<ten-dich-vu>.onrender.com/
https://<ten-dich-vu>.onrender.com/health
https://<ten-dich-vu>.onrender.com/?view=farm&lang=vi
https://<ten-dich-vu>.onrender.com/?view=comparison&lang=en
https://<ten-dich-vu>.onrender.com/report.json
~~~

Các địa chỉ trên là mẫu cấu trúc, chưa phải URL demo đang hoạt động.

- `/health` trả về JSON có `"status": "ok"`.
- Trang tổng quan và cả sáu mục điều hướng mở được; số liệu khí hậu hiện đầy đủ.
- Thử đổi mùa vụ, kịch bản, điều kiện tưới và xem kết quả.
- Đổi VI/EN, tăng cỡ chữ, mở menu trên điện thoại.
- Tải báo cáo JSON và kiểm tra nội dung.
- Xem **Logs** trên Render để chắc chắn không có traceback.

`/health` chỉ xác nhận Flask hoạt động; vẫn cần kiểm tra trang và JSON để xác nhận dữ liệu được nạp đúng.

## Đưa link công khai vào README và GitHub

Sau khi kiểm tra thành công:

1. Sửa mục **Demo công khai** trong `README.md` thành liên kết thật, ví dụ cú pháp `[Mở RiceShift](URL_THAT_TU_RENDER)`.
2. Commit và push thay đổi README bằng quy trình Git thông thường.
3. Ở trang repo GitHub, mở **About → biểu tượng bánh răng → Website**, dán URL thật và lưu.

Sau đó có thể chia sẻ trực tiếp URL Render cho người khác; người xem không cần cài Python hay clone mã nguồn.

## Render Free và lần mở đầu tiên

Theo tài liệu Render, dịch vụ Free ngủ sau **15 phút** không có truy cập; lần mở lại có thể cần khoảng **một phút** để khởi động. Gói này phù hợp demo; nếu cần truy cập ổn định cho buổi trình bày, cân nhắc gói trả phí và xem chi phí trong tài khoản trước khi đổi gói. [Giới hạn Free hiện hành](https://render.com/docs/free).

## Xử lý lỗi thường gặp

| Hiện tượng | Kiểm tra |
| --- | --- |
| `No module named flask` / không tìm thấy Gunicorn | Build dùng `RiceShift/requirements-web.txt`. |
| `No module named web` | Root Directory để trống và Start Command có `--chdir RiceShift`. |
| `No module named frontend_i18n` | Đã commit cả `frontend_i18n.py` và `presentation_messages.py` trong RiceShift. |
| `t is undefined` | Kiểm tra bản `web.py` đã đăng ký `app.context_processor(frontend_context)`; deploy commit mới nhất. |
| Thiếu dữ liệu NASA | Kiểm tra payload JSON đã được commit đúng đường dẫn, phân biệt chữ hoa/thường trên Linux. |
| Không tìm thấy cổng HTTP | Start Command có `--bind 0.0.0.0:$PORT`. |
| Trang trắng, lỗi 500 | Xem traceback trong Render Logs rồi kiểm tra template và các module đi kèm. |
| Link mở chậm sau một thời gian | Chờ dịch vụ Free khởi động lại; kiểm tra trạng thái deploy và Logs nếu vẫn lỗi. |
