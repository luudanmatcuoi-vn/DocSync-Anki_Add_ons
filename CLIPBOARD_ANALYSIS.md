# Clipboard Word / Google Docs

Phân tích dựa trên `clipboard_inspector.txt` do người dùng cung cấp. Đây là log clipboard qua trình duyệt, không phải bản dump Win32 gốc; log không đủ để khẳng định Qt là nguyên nhân duy nhất làm mất ảnh.

| Thuộc tính | Google Docs trong mẫu | MS Word trong mẫu |
|---|---|---|
| Bold | `span`, `font-weight:700` | `<b>` |
| Italic | `font-style:italic` | `<i>` |
| Underline | `text-decoration:underline` | `<u>` |
| Cỡ chữ | `font-size:16pt` | `font-size:16.0pt`, span lồng nhau |
| Highlight | `background-color:#ffff00` | `background:yellow` |
| Màu chữ | `color:#ff0000` | `color:red` |
| Ảnh | data URI PNG base64 | file URI trong thư mục `msohtmlclip1`, kèm VML trong conditional comment; RTF cũng chứa PNG và bản dự phòng |

Docs có wrapper `<b style="font-weight:normal">`: không được hiểu wrapper này là bold. Word dùng cả nháy đơn, xuống dòng trong thuộc tính, lớp MsoNormal và markup Office. Regex cũ chỉ đọc style nháy kép, bỏ font-size và background shorthand. Parser mới đọc HTML bằng BeautifulSoup, truyền style từ cha xuống con rồi ghi các thuộc tính định dạng rõ ràng lên span; bỏ head/script/comment, chuyển đoạn và br thành ranh giới dòng. Giá trị CSS hợp lệ như `red` và `#ff0000` có cùng ý nghĩa, không cần đồng nhất chuỗi ký tự. Đây là bộ hỗ trợ định dạng inline, không phải bộ dựng toàn bộ CSS stylesheet/Word layout.

## Quy tắc ảnh

- Export mặc định file URI, xuống dòng, `(filename.ext)`. File không còn trong media vẫn xuất tên để giữ tham chiếu.
- Dòng tên ảnh được nhận diện khi toàn bộ dòng là tên trong ngoặc, có phần mở rộng ảnh; không coi mọi ngoặc đơn trong văn bản là ảnh.
- Nếu tên tồn tại trong media: giữ ảnh đó, bỏ qua ảnh đi kèm. Nếu chỉ còn tên thì khôi phục img tham chiếu.
- Nếu tên chưa tồn tại và có ảnh ở dòng liền trước: lưu ảnh với tên đó. Nếu cả file và ảnh đều không có, giữ tham chiếu cũ, không đoán nội dung ảnh.
- Ảnh không có tên: lưu tên UUID, không so hash, kể cả khi nội dung trùng nhau.
- Ảnh được ghép với tên trong cùng field, không ghép xuyên field/note.

## Clipboard và hiệu năng

Import chỉ đọc Windows `HTML Format` bằng pywin32, cắt CF_HTML theo offset **byte** rồi giải mã UTF-8; không đi qua QTextEdit hoặc Qt clipboard. Cần cài dependency trong `requirements.txt` vào môi trường Python thực sự chạy Anki. Nếu pywin32 chưa có hoặc đang chạy hệ điều hành khác, UI báo lỗi rõ ràng; không tự chuyển sang Qt.

Export dựng preview đường dẫn một lần; nếu chọn trên 100 note thì chỉ render 20 note đầu, kèm dòng nhắc rằng nút copy sẽ copy toàn bộ. Preview chỉ đọc, không dùng làm nguồn dữ liệu export. Khi bấm copy, dựng toàn bộ dữ liệu theo chế độ đã chọn trong QThread; chuyển base64 dùng tối đa 4 worker đọc/encode các file khác nhau, mỗi filename chỉ encode một lần trong một lần dựng. Không dựng preview base64 khổng lồ trong QTextEdit và không encode lại khi copy. Copy ghi CF_HTML (offset byte UTF-8) và CF_UNICODETEXT trực tiếp qua pywin32, không dùng Qt clipboard. Việc cấp phát/copy dữ liệu clipboard rất lớn vẫn có chi phí; đa luồng không làm mất chi phí bộ nhớ của base64.

Ảnh Word mới có file URI cần file tạm còn truy cập được. Nếu file mất, import báo lỗi thay vì bỏ ảnh hoặc gán nhầm ảnh. Chưa có fallback giải mã RTF/EMF/WMF hoặc ánh xạ ảnh VML; không gán ảnh bitmap clipboard chung vào từng vị trí khi không biết tương ứng. Ảnh HTTPS được tải với TLS verification, timeout, giới hạn 32 MiB; URL yêu cầu phiên đăng nhập có thể không dùng được.

## Kiểm thử

`QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`

Có fixture HTML định dạng rút từ chính file mẫu, đã bỏ payload ảnh và conditional comment. Kiểm thử parser, CF_HTML UTF-8 byte offset, quy tắc tên ảnh, UUID, tạo/cập nhật note trong collection Anki thật và hai chế độ export. Windows pywin32, clipboard giữa ứng dụng thật, responsive UI với tài liệu lớn và RTF/VML cần kiểm tra trên Windows; Linux không xác nhận được các phần đó.
