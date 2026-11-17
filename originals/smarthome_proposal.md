# **PROPOSAL NGHIÊN CỨU & TRIỂN KHAI EDGE AI CHO SMARTHOME ĐA GIAO THỨC**

## *Tích hợp bổ sung vào hệ thống KNX / NiCe hiện hữu*

Bản đề xuất kỹ thuật để thảo luận

15/10/2026

**Nguyên tắc:** tận dụng hệ thống tự động hóa hiện có; không thay đổi bus hoặc cấp quyền điều khiển trực tiếp cho mô hình AI trước khi có kiểm thử.

## **Mục lục**

* 00 — Tóm tắt điều hành và quyết định cần thống nhất

* 01 — Bối cảnh và hiểu biết hiện tại về hệ thống

* 02 — Mục tiêu, phạm vi nghiên cứu

* 03 — EdgeAI trong đề xuất này

* 04 — Kiến trúc hệ thống đề xuất

* 05 — Use-case và thứ tự ưu tiên

* 06 — Lựa chọn phần cứng và dự toán

* 07 — Phần mềm, model và MLOps

* 08 — Tích hợp giao thức

* 09 — Điều khiển an toàn, quyền riêng tư và độ tin cậy

* 10 — Phương pháp đánh giá

* 11 — Kết luận

* Phụ lục A — Mẫu command request có kiểm soát

* Phụ lục B — Danh mục tài liệu tham khảo

* Phụ lục C — Danh sách phần cứng và phương pháp benchmark

# **Tóm tắt điều hành**

Đề xuất nghiên cứu cách bổ sung Edge AI vào hệ Smarthome nhiều giao thức dựa trên KNX và NiCe Series, trong đó NiCe 1 Central hoặc NiCe Pro là bộ điều khiển trung tâm. Mục tiêu không phải thay thế hệ thống tự động hóa hiện hữu hoặc nhúng AI vào tất cả module, mà tạo thêm một **lớp suy luận ngữ cảnh cục bộ** có thể khai thác dữ liệu từ cảm biến/camera và trạng thái thiết bị, sau đó gửi các yêu cầu điều khiển đã được kiểm tra qua giao diện tích hợp phù hợp.

**Đề xuất kiến trúc ban đầu:** một Edge Gateway độc lập trên mạng LAN, chạy inference và xử lý ngữ cảnh; LogicMachine/NiCe tiếp tục làm lớp tích hợp/điều khiển hiện hữu; adapter của từng giao thức đảm nhiệm ánh xạ lệnh và trạng thái. Mô hình AI không được truy cập trực tiếp bus hoặc tự phát lệnh tùy ý. Logic an toàn, thao tác thủ công, liên động và các chức năng cơ bản phải duy trì được khi AI/Gateway/Internet gặp sự cố.

**PoC (Proof of Concept) ưu tiên:** một module NiCe đã xác minh giao diện điều khiển và cấu hình; kết hợp dữ liệu hiện diện và độ rọi để xác định phòng đang sử dụng và đề xuất/điều chỉnh ánh sáng, thay đổi hoạt cảnh. Giai đoạn đầu chạy *shadow mode* (AI dự đoán nhưng chưa điều khiển), sau khi đánh giá lỗi mới cho phép điều khiển giới hạn. Đây là bài toán có phạm vi nhỏ, đo lường được và ít rủi ro hơn triển khai ngay nhận diện hành vi phức tạp hoặc điều khiển HVAC toàn nhà.

**Kết quả mong đợi:** kiến trúc logic/luồng dữ liệu, danh mục phần cứng và giao thức đã xác minh, PoC có số liệu so sánh với rule-based baseline, đánh giá độ trễ/chất lượng/điện năng, mô hình rủi ro-bảo mật, và khuyến nghị có nên mở rộng sang camera/audio/HVAC hay không.

# **1\. Bối cảnh và hiểu biết hiện tại về hệ thống**

Theo ghi chú từ buổi training trước, KNX là tiêu chuẩn tự động hóa tòa nhà; thiết bị được cấu hình qua ETS và trao đổi qua KNX bus. Trong triển khai được mô tả, KNX TP dùng cặp dây xoắn đôi; KNX power supply kết hợp choke cấp nguồn và tách nguồn DC khỏi tín hiệu bus. LogicMachine được sử dụng làm interface và có thể đóng vai trò trung gian giữa KNX và hệ thống CAN. NiCe Series hướng tới phân chia module theo khu vực/tầng; NiCe 1 Central và NiCe Pro được mô tả là hai lựa chọn bộ điều khiển trung tâm, dùng một trong hai cho một công trình và tích hợp LogicMachine KNX. Các module NiCe kết nối thành hệ thống qua dây EIB.

## **1.1. Vấn đề cần giải quyết**

* Hệ tự động hóa truyền thống có thể điều khiển theo group address, trạng thái cảm biến và rule đã cấu hình, nhưng chưa chắc khai thác được ngữ cảnh phức tạp hoặc dự báo thói quen.

* Các giao thức KNX, CAN, DALI và thiết bị thường có mô hình dữ liệu/giao diện khác nhau; AI không thể phát một lệnh chung và giả định mọi thiết bị đều hiểu.

* Camera/audio tạo lượng dữ liệu lớn và có tính riêng tư; gửi dữ liệu thô lên cloud liên tục có thể không cần thiết.

* Quyết định AI mang tính xác suất, trong khi điều khiển điện/cơ khí cần giới hạn, phản hồi trạng thái, khả năng ghi vết và hành vi xác định khi lỗi.

## **1.2. Cơ hội**

Edge AI có thể biến dữ liệu hiện trường thành các event có ý nghĩa như room\_occupied, reading\_activity, approach\_detected hoặc energy\_anomaly. Một lớp tích hợp sẽ kết hợp các event này với trạng thái KNX/DALI/CANx, rồi yêu cầu hệ thống điều khiển hiện hữu thực thi logic phù hợp. Cách tiếp cận này cho phép thử nghiệm AI mà không phải thay thế toàn bộ nền tảng automation.

# **2\. Mục tiêu, phạm vi nghiên cứu**

## **2.1. Mục tiêu chính**

1. Đề xuất kiến trúc Edge AI tương thích về mặt tích hợp với hệ thống KNX/NiCe hiện hữu.

2. Xác định vị trí hợp lý để chạy AI: camera/thiết bị đầu cuối, vi điều khiển TinyML hay gateway cục bộ.

3. Xây dựng một PoC có thể lặp lại và so sánh với rule-based baseline..

4. Định lượng hiệu quả và chi phí: chất lượng inference, end-to-end latency, false actions, điện năng, khả năng hoạt động offline và yêu cầu vận hành.

## **2.2. Phạm vi giai đoạn đầu**

**Trong phạm vi:** khảo sát hiện trạng; sơ đồ vật lý và logic; read-only integration; một phòng; nhận diện hiện diện/ngữ cảnh đơn giản; điều khiển một nhóm đèn; logging, đánh giá, bảo mật cơ bản và xử lý lỗi.

**Ngoài phạm vi PoC đầu tiên:** điều khiển HVAC toàn nhà; nhận diện danh tính/biometric; huấn luyện online tự động trên thiết bị.

# **3\. EdgeAI trong đề xuất này**

EdgeAI là việc chạy một phần hoặc toàn bộ inference gần nơi dữ liệu phát sinh. Cần phân biệt:

* **Training:** huấn luyện/cập nhật trọng số model, thường thực hiện trên workstation/server ở giai đoạn đầu.

* **Inference:** dùng model đã huấn luyện để dự đoán trên dữ liệu mới; đây là phần dự kiến chạy tại EdgeAI Gateway hoặc thiết bị thông minh.

* **Automation/policy:** logic xác định xem dự đoán có được phép tạo lệnh hay không. AI đưa ra bằng chứng/ngữ cảnh; policy engine mới quyết định yêu cầu điều khiển.

| Kiến trúc | Điểm mạnh | Hạn chế | Vai trò đề xuất |
| :---- | :---- | :---- | :---- |
| CloudAI | Có thể dùng compute lớn; quản lý tập trung | Phụ thuộc kết nối; truyền dữ liệu nhạy cảm; latency mạng | Huấn luyện, phân tích dài hạn nếu được phép |
| EdgeAI | Phản hồi cục bộ; giảm media truyền ra ngoài; có thể hoạt động khi mất Internet | Tài nguyên phần cứng hạn chế; cần tự quản lý cập nhật/giám sát | Inference và quyết định nhanh trong nhà |
| Hybrid AI | Tác vụ nhạy thời gian chạy tại nhà, training/analytics có thể dùng server | Kiến trúc vận hành phức tạp hơn | Định hướng mở rộng sau PoC |

# **4\. Kiến trúc hệ thống đề xuất**

## **4.1. Nguyên tắc thiết kế**

1. **Add-on, không replace:** giữ nguyên điều khiển KNX/NiCe/LogicMachine hiện hữu; Edge AI là thành phần bổ sung.

2. **Local-first:** xử lý media tại LAN khi có thể; cloud là tùy chọn cho training/analytics, không phải dependency của logic phản ứng cơ bản.

3. **AI không trực tiếp điều khiển bus:** model chỉ trả kết quả dự đoán; policy/safety guard mới cho phép tạo yêu cầu điều khiển.

4. **Fail-safe và manual override:** khi Gateway hỏng, model lỗi, dữ liệu cũ hoặc mất Internet, tự động hóa cơ bản và điều khiển thủ công vẫn được ưu tiên trong phạm vi hệ thống hỗ trợ.

## **4.2. Sơ đồ kiến trúc logic**

![Sơ đồ kiến trúc logic đề xuất][image1]

**Lưu ý:** Đối chiếu với sơ đồ kiến trúc của KNX và NiCe hiện tại để xem xét lại sơ đồ kiến trúc này.

## **4.3. Các lớp chức năng**

| Lớp | Thành phần | Trách nhiệm |
| :---- | :---- | :---- |
| Field/Perception | Cảm biến KNX, camera, mic, sensor IP | Thu dữ liệu, timestamp và trạng thái thiết bị |
| Protocol/Integration | NiCe/LogicMachine, KNX interface, DALI gateway, CANx adapter, MQTT/API | Đọc object/trạng thái, ánh xạ command và xác nhận phản hồi |
| Edge compute | Pi/mini PC/Jetson/industrial PC tùy workload | Inference, state fusion, lưu sự kiện |
| Policy & safety | Rule/state machine, limits, override, cooldown | Quyết định chấp nhận/từ chối action |
| Observability | Log, metric, health check, clock sync | Audit, benchmark, cảnh báo, chẩn đoán |
| Optional server/cloud | Training, model registry, thống kê | Huấn luyện, đánh giá, phân phối model có kiểm soát |

## **4.4. Luồng dữ liệu và luồng điều khiển**

**Data flow:** cảm biến/camera → ingestion → chuẩn hóa timestamp/đơn vị/trạng thái → feature extraction → inference → kết quả có confidence và model version → state/context fusion → log.

**Control flow:** kết quả AI → kiểm tra độ tin cậy và độ mới dữ liệu → policy kiểm tra giới hạn/ưu tiên thủ công/interlock → allowlist command → adapter LogicMachine/protocol → actuator → feedback/status readback → log kết quả và đối chiếu với yêu cầu ban đầu.

**Ví dụ:** camera chỉ tạo person\_detected/zone\_id; cảm biến KNX cung cấp lux và trạng thái công tắc; policy suy ra yêu cầu “tăng sáng vùng đọc”. Gateway gửi yêu cầu qua giao diện được hỗ trợ; LogicMachine/module phù hợp thực thi và trạng thái đèn được đọc lại.

### **4.5. Distributed Device Edge AI — Phân bổ suy luận tại thiết bị đầu cuối**

Bên cạnh kiến trúc Edge AI Gateway tập trung, hệ thống cần xem xét khả năng triển khai inference trực tiếp trên một số thiết bị đầu cuối như camera AI, microphone/audio node hoặc các thiết bị nhúng có năng lực tính toán phù hợp. Mục tiêu là giảm lượng dữ liệu thô phải truyền qua mạng, giảm tải xử lý tại Gateway và hỗ trợ phản hồi cục bộ khi phù hợp.

1. **Nguyên tắc phân bổ**

Hệ thống sử dụng kiến trúc phân tầng, trong đó mỗi thành phần đảm nhiệm nhóm tác vụ phù hợp với tài nguyên và yêu cầu vận hành:

* **Device Edge AI:** xử lý dữ liệu gần nguồn phát sinh, trích xuất đặc trưng và tạo event có cấu trúc. Ví dụ: phát hiện người hoặc vùng hoạt động từ camera; phân loại âm thanh hoặc nhận diện wake-word tại microphone.  
* **Edge AI Gateway:** hợp nhất event từ nhiều nguồn, kết hợp với trạng thái KNX/DALI/CANx, suy luận ngữ cảnh ở cấp phòng hoặc toàn nhà và chạy policy engine.  
* **Automation & Control:** LogicMachine/NiCe cùng các interface và adapter được xác minh tiếp tục đảm nhiệm việc tích hợp giao thức, thực thi lệnh và cung cấp phản hồi trạng thái.  
* **Server/Cloud tùy chọn:** hỗ trợ huấn luyện, đánh giá, quản lý phiên bản và phân tích dài hạn; không phải thành phần bắt buộc của đường điều khiển cục bộ.

Không yêu cầu mọi thiết bị đều phải tích hợp AI. Các cảm biến đo lường thông thường tiếp tục cung cấp dữ liệu trực tiếp; chỉ triển khai inference tại thiết bị khi có lợi ích rõ ràng về độ trễ, băng thông, quyền riêng tư hoặc mức tải xử lý.

2. **Trao đổi dữ liệu giữa các tầng**

Thiết bị đầu cuối ưu tiên gửi event và metadata thay vì dữ liệu media thô khi tác vụ không cần truyền dữ liệu gốc. Event cần có định danh nguồn, phòng/khu vực, timestamp, loại sự kiện, giá trị hoặc nhãn, độ tin cậy nếu có, phiên bản model, chất lượng dữ liệu và thời hạn hiệu lực.

Gateway chịu trách nhiệm kiểm tra tính hợp lệ và độ mới của event trước khi hợp nhất với trạng thái hệ thống. Các event do model tạo ra chỉ là đầu vào cho quá trình suy luận và policy; chúng không mặc nhiên trở thành lệnh điều khiển.

3. **Phạm vi triển khai**

Trong PoC ban đầu, Gateway tập trung vẫn là kiến trúc cơ sở. Nhánh Device Edge AI được đánh giá bằng cách chạy cùng một tác vụ trên Gateway và trên một thiết bị đầu cuối có khả năng inference. Việc mở rộng chỉ được đề xuất khi kết quả đo chứng minh được lợi ích đủ lớn và đáp ứng các yêu cầu về độ chính xác, độ trễ, điện năng, quyền riêng tư và khả năng vận hành.

4. **Điều kiện và rủi ro**

Cần kiểm tra khả năng tương thích giữa model, runtime và phần cứng; tài nguyên RAM/bộ nhớ; nhiệt độ và công suất; độ đồng bộ timestamp; bảo mật giao tiếp; cập nhật và rollback model; cũng như hành vi khi node hoặc mạng bị lỗi. Khi mất kết nối hoặc dữ liệu không hợp lệ, Gateway phải từ chối các hành động không đủ điều kiện và hệ thống tự động hóa hiện hữu tiếp tục đảm nhiệm các chức năng cơ bản trong phạm vi thiết kế hỗ trợ.

# **5\. Use-case và thứ tự ưu tiên**

| Ưu tiên | Use-case | Input | Output mong muốn | Khuyến nghị |
| :---- | :---- | :---- | :---- | :---- |
| P0 | Occupancy từ cảm biến | PIR/mmWave, cửa, lux, trạng thái KNX | Xác suất/phân loại phòng có người | Baseline đầu tiên; rủi ro thấp và dễ kiểm tra |
| P1 | Occupancy camera tại chỗ | Video xử lý local, trạng thái cảm biến | Event có người/vùng hoạt động | Chỉ thêm nếu sensor-only chưa đủ; cần privacy review |
| P1 | Lighting context | Occupancy, lux, thời gian, override, preference | Mức sáng/scene đề xuất | Ghép với DALI/KNX sau khi xác minh adapter |
| P2 | Dự báo HVAC | Occupancy, nhiệt độ/độ ẩm, cửa, lịch | Dự báo nhu cầu hoặc đề xuất setpoint | Chạy shadow mode; cần thu dữ liệu dài hơn |
| P2 | Hành vi/thói quen người dùng | Event theo thời gian, lịch, context | Scene cá nhân hóa | Tránh học tự động không kiểm soát; cần cơ chế opt-out |
| P3 | Âm thanh bất thường/ngã/an ninh | Audio/video | Event cảnh báo | Chỉ là lớp bổ sung; không thay hệ báo động/cháy đạt chuẩn |

## **5.1. Kịch bản minh họa A — Ánh sáng theo hoạt động**

1. Hệ thống phát hiện có người trong phòng khách.

2. Edge AI tổng hợp camera/sensor, lux, giờ trong ngày và trạng thái đèn.

3. Model tạo nhãn ngữ cảnh (ví dụ reading, nếu model/label set có hỗ trợ) cùng confidence. Không suy diễn danh tính nếu không cần.

4. Policy kiểm tra ngưỡng lux, giới hạn sáng, thời gian giữ trạng thái, thao tác công tắc gần nhất và giới hạn số lệnh.

5. Yêu cầu đi qua LogicMachine/adapter đã xác minh tới nhóm đèn.

6. Đọc lại trạng thái, ghi nhận lệnh thành công/thất bại và mọi lần người dùng override.

## **5.2. Kịch bản minh họa B — Dự đoán người dùng sắp về nhà**

Hệ thống có thể học quy luật theo thời gian từ các event được phép thu thập và dùng chúng để **đề xuất** bật sẵn ánh sáng/HVAC. Không nên tự động bật bình nóng lạnh hoặc thiết bị tiêu thụ lớn chỉ từ suy đoán hành vi. Giai đoạn đầu chạy shadow/advisory, yêu cầu điều kiện xác nhận (ví dụ vị trí thiết bị/door event có consent hoặc lịch do người dùng cấu hình), giới hạn công suất và có override.

## **5.3. Kịch bản an toàn**

Phát hiện từ camera/audio có thể tạo event bổ sung, nhưng các chức năng báo cháy, chống ngập, emergency shutdown và bảo vệ con người phải dựa vào cảm biến/hệ thống chuyên dụng và logic an toàn thích hợp. Không sử dụng độ tin cậy của model AI làm bằng chứng duy nhất để vô hiệu hóa báo động hoặc kích hoạt thiết bị nguy hiểm.

# **6\. Lựa chọn phần cứng**

## **6.1. Khuyến nghị theo giai đoạn**

**Giai đoạn 0** — Không mua phần cứng AI chuyên dụng: dùng workstation/laptop hoặc máy Linux hiện có để chuẩn hóa schema sự kiện, mock adapter, xây rule-based baseline, chuẩn bị dữ liệu v\\

à chạy thử model.

**Giai đoạn 1** — Gateway PoC: ưu tiên mini PC x86 hoặc Raspberry Pi 5\. Mục tiêu là xác minh khả năng tiếp nhận dữ liệu, hợp nhất trạng thái, thực thi chính sách, logging và khả năng vận hành LAN/offline trước khi tối ưu inference.

**Giai đoạn 2** — Tăng tốc thị giác: so sánh Pi 5 \+ AI HAT+, Jetson Orin Nano Super, hoặc bộ tăng tốc phần cứng phù hợp. Chỉ chọn sau khi chạy đúng model/dữ liệu/camera dự kiến và đo latency, thông lượng, công suất, nhiệt độ cùng độ chính xác.

**Giai đoạn 3** — Gateway nhúng/công nghiệp hoặc nhiều camera: mở rộng khảo sát TI AM69A, AMD Ryzen Embedded 8000\. Các nền tảng này phù hợp hơn khi có yêu cầu về vòng đời, nhiều camera, giao tiếp công nghiệp, khả năng mở rộng và thiết kế sản phẩm.

**Nhánh Device Edge AI:** thử một camera/vision node có inference tại chỗ và một node MCU/âm thanh. Chỉ phân tán inference khi benchmark chứng minh lợi ích về độ trễ, băng thông, quyền riêng tư hoặc tải Gateway.

## **6.2. Đề xuất lựa chọn phần cứng theo giai đoạn**

| Giai đoạn / Mục tiêu | Phần cứng đề xuất | Lý do lựa chọn và điều kiện ra quyết định |
| :---- | :---- | :---- |
| **Giai đoạn 0 — Xây baseline, chưa mua AI chuyên dụng** | Dùng laptop/workstation hoặc máy Linux hiện có. | Không phát sinh chi phí phần cứng khi đang chuẩn hóa schema event, mock adapter, xây rule-based baseline, thu dữ liệu và kiểm thử policy. |
| **Giai đoạn 1 — Gateway trung tâm cho PoC một phòng** | Mini PC x86 Intel N100/N97. | Lựa chọn cân bằng cho gateway điều khiển 24/7: nhiều dịch vụ Docker, API/MQTT, database nhẹ, logging và state fusion.  |
|  | Raspberry Pi 5\. | Phù hợp khi workload nhẹ, kích thước nhỏ và yêu cầu điện năng thấp. Có thể chạy Linux, Docker và các dịch vụ điều khiển; CPU có thể xử lý một số mô hình nhỏ.   |
|  |  | [N97 vs N100 vs Raspberry Pi 5: Which Is Right For You?](https://youtu.be/O1j_efFxT1E?si=hijbknYNO-i0wjB_) |
| **Giai đoạn 2 — Thử nghiệm inference camera/vision** | NVIDIA Jetson Orin Nano Super.  | Vừa làm gateway vừa chạy các workload AI. Có khả năng giải quyết các luồng video và inference chạy đồng thời, xử lý mô hình và latency. Cân nhắc nếu workload vision là một phần quan trọng của hệ thống.  [NVIDIA's \$249 Secret Weapon for Edge AI - Jetson Orin Nano Super: Driveway Monitor](https://www.youtube.com/watch?v=QHBr8hekCzg) [The \$249 AI Computer from NVIDIA is NOT like a Raspberry Pi](https://youtu.be/Wtjz2qlh1SI?si=pd32m8ui7OoH0uP8) |
|  | Raspberry Pi 5 \+ AI HAT+ 26 TOPS cho model vision tương thích Hailo | Pi 5 làm gateway trung tâm, AI HAT+ làm bộ tăng tốc vision để thử person/occupancy detection. Module Hailo rời cần host PCIe/M.2, driver/runtime và tản nhiệt tương thích. |
|  | Mini PC \+ Hailo-8/8L rời | Gateway x86 chạy nhiều dịch vụ 24/7 và thêm accelerator rời để đảm nhiệm phần inference, với điều kiện host tương thích. Mini PC phải có khe PCIe/M.2 tương thích về giao tiếp điện, key và kích thước  |
| **Nhánh song song — Device Edge AI cho tác vụ chuyên biệt** Node có thể xử lý dữ liệu ngay tại chỗ, rồi chỉ gửi sự kiện hoặc kết quả đã cấu trúc. Cách này có thể giảm băng thông, độ trễ và lượng dữ liệu riêng tư phải truyền đi.  | ESP32-S3  | Node âm thanh. Phát hiện từ khóa đánh thức, phân loại âm thanh. Có thể đọc cảm biến, trích xuất đặc trưng và chạy mô hình nhỏ như TinyML để nhận diện trạng thái |
|  | Sipeed MaixCAM/Kendryte K230  | Node camera. Có thể chạy mô hình phát hiện người, suy luận tại biên và chỉ gửi các sự kiện cần thiết.  |
| **Giai đoạn 3 — Mở rộng nhiều camera hoặc hướng sản phẩm công nghiệp** | Jetson Orin NX | Xử lý nhiều luồng camera, phát hiện người, theo dõi đối tượng và thực hiện các tác vụ vision khác trên cùng nền tảng.  Xem xét khi benchmark cho thấy Pi, mini PC N97 hoặc Jetson Orin Nano không còn đáp ứng được số luồng, độ trễ hay độ chính xác mục tiêu.  |
|  | Texas Instruments AM69A  | SoC tích hợp CPU Arm, các bộ tăng tốc deep learning và các khối xử lý hình ảnh chuyên dụng. Xem xét khi hệ thống có nhiều camera, cần giải mã video, xử lý hình ảnh đầu vào, chuyển đổi định dạng, resize, chạy inference và hậu xử lý.  |
|  | AMD Ryzen Embedded 8000  | Bộ xử lý nhúng x86-64, tích hợp CPU, GPU và NPU trên SoC. Có thể làm gateway tổng hợp, có lợi ích về vòng đời, tích hợp phần cứng và khả năng vận hành lâu dài. |
|  | Jetson AGX Orin  | Năng lực tính toán và bộ nhớ cao hơn ở các cấu hình tương ứng. Chỉ xem xét nếu Jetson Orin NX không đáp ứng đủ. |

## **6.3. Thiết bị đầu vào và thiết bị giao tiếp cần liệt kê**

Ưu tiên tận dụng cảm biến và interface đã có trong công trình. Chỉ bổ sung camera/microphone hoặc cảm biến mới.

| Nhóm thiết bị | Ví dụ phần cứng | Vai trò/dữ liệu |
| :---- | :---- | :---- |
| NiCe Series |  | Control plane, protocol mapping, feedback |
| Cảm biến hiện diện | KNX presence detector; PIR; mmWave radar | Occupancy, vùng hiện diện, thời gian không hoạt động |
| Độ rọi/ánh sáng | KNX lux sensor; lux sensor rời | Lighting context, kiểm tra đủ sáng |
| Môi trường | Nhiệt độ/độ ẩm/CO₂/TVOC/PM2.5 | HVAC context, comfort, phát hiện bất thường |
| Camera IP | Camera IP/PoE, RTSP/ONVIF nếu được hỗ trợ | Occupancy, person/zone detection, activity nhẹ |
| Camera CSI | Raspberry Pi Camera Module hoặc camera MIPI CSI tương thích board | Vision node gắn trực tiếp với SBC/SoC |
| Microphone/audio | USB microphone, I²S MEMS mic, microphone array | Wake-word, audio event classification, voice activity |
| Công tắc/nút nhấn/cửa | KNX push button, reed switch, door/window contact | Override, occupancy evidence, context |
| Thiết bị đầu vào audio/video tích hợp AI | Smart camera/edge AI camera có SoC/NPU | Phát event metadata mà không gửi toàn bộ media về Gateway |

## **6.4. Phụ kiện và kết nối cần xác minh trước khi mua**

• Gateway: nguồn đúng công suất, tản nhiệt chủ động/thụ động, SSD/NVMe hoặc storage bền, Ethernet và USB dự phòng; UPS nếu cần duy trì hệ thống.

• Accelerator: xác minh PCIe/M.2/USB, lane/băng thông, driver/runtime, hỗ trợ model, nguồn và nhiệt.

# **7\. Phần mềm, model và MLOps**

## **7.1. Stack khuyến nghị cho PoC**

| Hạng mục | Lựa chọn bắt đầu | Lý do / điểm cần kiểm tra |
| :---- | :---- | :---- |
| OS | Linux trên Pi/mini PC | Dễ cài runtime, quản lý service, log và quyền truy cập |
| AI development | Python, scikit-learn; PyTorch/TensorFlow khi cần DL | Dễ phân tích dữ liệu và lập baseline |
| Inference runtime | ONNX Runtime hoặc runtime chuyên dụng của target | Chọn theo model/export và phần cứng thực tế; benchmark trước khi chốt |
| Camera processing | OpenCV và pipeline phù hợp | Tách capture/preprocess khỏi policy; giới hạn FPS/độ phân giải nếu đủ dùng |
| API/service | Python service; REST hoặc MQTT tùy interface đã hỗ trợ | Giữ API/service tách khỏi model và actuator |
| State/log | SQLite cho PoC nhỏ; lưu trữ chuỗi thời gian khi cần mở rộng | Tránh xây database quá lớn trước khi biết nhu cầu |
| Automation UI | Dùng LogicMachine hiện có; dashboard phụ chỉ khi cần | Tránh có hai hệ thống cùng sở hữu logic điều khiển |
| Deployment | Docker Compose trên Linux | Quản lý service/version; cần thử quyền thiết bị và khởi động lại |
| Model packaging | Versioned artifacts, hash/signature, config version | Có rollback và khả năng tái lập benchmark |

## **7.2. Pipeline dữ liệu và huấn luyện**

1. **Inventory:** liệt kê cảm biến, group address/datapoint, trạng thái đèn, nhiệt độ, lịch và event có thể thu thập.

2. **Collect:** thu dữ liệu tối thiểu cần thiết; đồng bộ thời gian và ghi rõ phiên bản cấu hình.

3. **Label:** gán nhãn với hướng dẫn rõ ràng; không suy diễn nhãn từ output của chính model.

4. **Baseline:** xây rule-based và model thống kê đơn giản làm mốc so sánh.

5. **Train/evaluate:** chia train/validation/test theo ngày/tuần hoặc phiên sử dụng để tránh leakage; kiểm tra trường hợp hiếm.

6. **Optimize:** thử quantization/pruning/distillation nếu có căn cứ; đo trade-off accuracy–latency–RAM–power.

7. **Deploy:** đóng gói model kèm version, hash, threshold, label map và model card.

8. **Shadow mode:** model dự đoán, log output, không phát lệnh.

9. **Limited control:** bật cho một nhóm đèn với allowlist và manual override.

10. **Update/rollback:** chỉ phát hành model đã kiểm thử; có health check, rollback và lưu phiên bản trước.

# **8\. Tích hợp giao thức**

## **8.1. KNX**

* Ưu tiên lấy trạng thái qua KNXnet/IP hoặc API/interface mà hệ thống hiện tại hỗ trợ; LogicMachine có thể là điểm tích hợp nếu đúng phiên bản/cấu hình.

* Lập danh sách group address, datapoint type, đơn vị, quyền đọc/ghi, giá trị hợp lệ và trạng thái feedback.

* Không quét/ghi bus thực tùy tiện; thử trên group/object cho PoC và giữ snapshot cấu hình ETS trước thay đổi.

* Kiểm tra KNX IP Secure hoặc biện pháp kiểm soát truy cập phù hợp với thiết bị hiện tại nếu được hỗ trợ.

## **8.2. LogicMachine**

Cần xác minh phiên bản phần cứng/firmware và các interface đã bật: API, MQTT, scripting, object access, quyền xác thực và cơ chế đọc trạng thái. EdgeAI Gateway nên gọi qua interface được hỗ trợ, không truy cập nội bộ hoặc phụ thuộc vào API không được tài liệu hóa.

## **8.3. Mô hình trạng thái chuẩn**

Để AI không gắn chặt vào từng giao thức, tạo schema nội bộ thống nhất. Ví dụ:

{  
  "event\_id": "uuid",  
  "timestamp": "2026-10-14T09:00:00+07:00",  
  "source": "living\_room\_camera",  
  "room\_id": "living\_room",  
  "event\_type": "occupancy\_estimate",  
  "value": "occupied",  
  "confidence": 0**.**91,  
  "model\_version": "occupancy-v0.1.0",  
  "ttl\_ms": 3000  
}

Schema thực tế cần định nghĩa datatype, unit, timestamp, quality, source, freshness/TTL, confidence, model version và quyền truy cập.

# **9\. Điều khiển an toàn, quyền riêng tư và độ tin cậy**

## **9.1. Safety guard tối thiểu**

* Allowlist theo room\_id, group address/object, command và giá trị hợp lệ.

* Confidence threshold và stale-data guard; nếu dữ liệu cũ/không đủ chắc chắn thì không tạo hành động mới.

* Hysteresis, cooldown, minimum on/off time và command rate limit để tránh bật/tắt liên tục.

* Manual override có ưu tiên rõ ràng và khoảng thời gian hiệu lực được cấu hình.

* Kiểm tra interlock/giới hạn tải trước khi phát lệnh.

* Readback/feedback và retry có giới hạn; log requested, sent, confirmed, failed riêng biệt.

* Watchdog, health check, restart policy và fallback khi model service/Gateway lỗi.

* Không cấp cho model quyền thay đổi cấu hình ETS, địa chỉ bus, firmware hoặc access control.

## **9.2. Privacy-by-design**

* Chỉ thu trường dữ liệu cần thiết; ưu tiên sensor-only trước camera/audio nếu đạt chất lượng đủ dùng.

* Nếu dùng camera/microphone, xử lý local, hạn chế lưu media thô, đặt retention rõ ràng, kiểm soát quyền truy cập và thông báo/consent phù hợp.

* Không nhận diện khuôn mặt/danh tính nếu chỉ cần occupancy hoặc activity.

* Bảo vệ credential; giới hạn MQTT/API bằng authentication và ACL; tách mạng IoT/management nếu hạ tầng cho phép.

## **9.3. Bảng rủi ro ban đầu**

| Rủi ro | Hậu quả | Giảm thiểu / kiểm chứng |
| :---- | :---- | :---- |
| False positive occupancy | Bật đèn/HVAC không cần thiết | Baseline, shadow mode, threshold, cooldown, feedback và override |
| False negative | Tắt đèn khi còn người | Kết hợp sensor; timeout an toàn; theo dõi override và false-off |
| Gateway/model crash | Mất tính năng AI | Tách service AI khỏi control; watchdog; hệ cũ tiếp tục hoạt động |
| Dữ liệu camera/mic lộ | Vi phạm riêng tư | Local processing, retention tối thiểu, ACL, không upload mặc định |
| Model drift | Chất lượng giảm theo thay đổi phòng/ánh sáng | Theo dõi metrics, kiểm định định kỳ, rollback model |
| Nhiệt/điện/storage không ổn định | Throttling hoặc mất dịch vụ | Benchmark dài hạn, nguồn phù hợp, storage bền và cảnh báo nhiệt |
| AI phát lệnh ngoài phạm vi | Tác động không mong muốn tới thiết bị | Policy engine, allowlist, rate limit, test fault/abuse |

# **10\. Phương pháp đánh giá**

## **10.1. Baseline cần so sánh**

1. Cấu hình điều khiển hiện có hoặc thao tác thủ công.

2. Rule-based baseline dễ giải thích (ví dụ occupancy \+ timeout).

3. Model ML nhẹ, nếu dữ liệu và bài toán hỗ trợ.

4. Model đã tối ưu và chạy trên thiết bị mục tiêu.

## **10.2. Chỉ số đo**

* **Model quality:** precision, recall, F1, confusion matrix, false-positive/false-negative theo thời điểm và điều kiện phòng.

* **Latency:** inference latency và end-to-end từ event đến trạng thái actuator; báo cáo p50/p95/p99 nếu lượng mẫu đủ.

* **Resource:** peak RAM, CPU/NPU utilization, storage growth, công suất trung bình, nhiệt độ và thermal throttling.

* **Automation:** số lần bật/tắt sai mỗi ngày, thời gian bật đèn khi phòng trống, manual override, command failure/loop.

* **Robustness:** hành vi khi mất WAN, mất LAN, sensor offline, dữ liệu stale, restart, model crash, lệnh timeout và rollback.

* **Privacy:** số byte media thô gửi ra WAN; mục tiêu local-only là không có media thô đi ra ngoài trừ khi được chủ động cấu hình.

# **11\. Kết luận**

Định hướng được đề xuất là **bổ sung một EdgeAI Gateway cục bộ**. Gateway thực hiện inference và chuẩn hóa ngữ cảnh; LogicMachine/NiCe tiếp tục đảm nhiệm phần tích hợp/automation hiện có; adapter đúng giao thức thực thi yêu cầu và cung cấp feedback. Điều này tách riêng AI khỏi đường điều khiển cốt lõi, giúp thử nghiệm và rollback dễ hơn.

# **Phụ lục A — Mẫu command request có kiểm soát**

{  
  "command\_id": "uuid",  
  "issued\_at": "2026-10-14T09:00:00+07:00",  
  "source": "edge-policy-engine",  
  "target": "living\_room.lighting\_group",  
  "action": "set\_brightness",  
  "value": 55,  
  "unit": "percent",  
  "reason": "occupancy\_and\_low\_lux",  
  "confidence": 0**.**91,  
  "expires\_at": "2026-10-14T09:00:03+07:00",  
  "policy\_version": "lighting-policy-v0.1",  
  "requires\_feedback": **true**  
}

# **Phụ lục B — Danh mục tài liệu tham khảo**

## **B.1. Nền tảng EdgeAI và TinyML**

**\[1\]** Zhou et al. (2019), *Edge Intelligence: Paving the Last Mile of Artificial Intelligence With Edge Computing*. arXiv:1905.10083 ([https\://arxiv.org/abs/1905.10083](https://arxiv.org/abs/1905.10083))

**\[2\]** Soro (2021), *TinyML for Ubiquitous Edge AI*. arXiv:2102.01255 ([https\://arxiv.org/abs/2102.01255](https://arxiv.org/abs/2102.01255))

**\[3\]** Han, Mao & Dally (2016), *Deep Compression: Compressing Deep Neural Networks with Pruning, Trained Quantization and Huffman Coding*. arXiv:1510.00149 ([https\://arxiv.org/abs/1510.00149](https://arxiv.org/abs/1510.00149))

**\[4\]** Edge Impulse, *What is Edge Machine Learning?* Documentation ([https\://docs.edgeimpulse.com/docs/concepts/what-is-edge-machine-learning](https://docs.edgeimpulse.com/docs/concepts/what-is-edge-machine-learning))

## **B.2. Smart Home / dữ liệu**

**\[5\]** Washington State University, *CASAS Smart Home Datasets*. Dataset catalogue ([https\://casas.wsu.edu/datasets/](https://casas.wsu.edu/datasets/))

**\[6\]** Kelly & Knottenbelt (2015), *The UK-DALE dataset*. Scientific Data ([https\://www\.nature.com/articles/sdata20157](https://www.nature.com/articles/sdata20157))

**\[7\]** Home Assistant, *Local Voice Assistant*. Documentation ([https\://www\.home-assistant.io/voice\_control/voice\_remote\_local\_assistant](https://www.home-assistant.io/voice_control/voice_remote_local_assistant))

## **B.3. Chuẩn, phần cứng và runtime**

**\[8\]** KNX Association, *KNX Standard V3.0 / KNX IoT*. Overview ([https\://www\.knx.org/news/knx-standard-v30-bringing-internet-things-knx-specifications](https://www.knx.org/news/knx-standard-v30-bringing-internet-things-knx-specifications))

**\[9\]** KNX Support, *KNX IP Secure*. Documentation ([https\://support.knx.org/hc/en-us/articles/360012666599-KNX-IP-Secure](https://support.knx.org/hc/en-us/articles/360012666599-KNX-IP-Secure))

**\[10\]** Digital Illumination Interface Alliance, *DALI* và *Colour Control / DT8*. DALI Alliance ([https\://www\.dali-alliance.org/](https://www.dali-alliance.org/)) · Colour control ([https\://www\.dali-alliance.org/dali/colour.html](https://www.dali-alliance.org/dali/colour.html))

**\[11\]** Raspberry Pi, *AI HAT+ documentation*. Official docs ([https\://www\.raspberrypi.com/documentation/accessories/ai-hat-plus.html](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html))

**\[12\]** NVIDIA, *Jetson Orin Nano Developer Kit User Guide*. Official docs ([https\://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/))

**\[13\]** Espressif, *ESP-DL User Guide for ESP32-S3*. Official docs ([https\://docs.espressif.com/projects/esp-dl/en/release-v1.1/esp32s3/introduction.html](https://docs.espressif.com/projects/esp-dl/en/release-v1.1/esp32s3/introduction.html))

**\[14\]** STMicroelectronics, *STM32N6 Series*. Product documentation ([https\://www\.st.com/en/microcontrollers-microprocessors/stm32n6-series.html](https://www.st.com/en/microcontrollers-microprocessors/stm32n6-series.html))

**\[15\]** ONNX Runtime, *Execution Providers*. Official docs ([https\://onnxruntime.ai/docs/execution-providers/](https://onnxruntime.ai/docs/execution-providers/))

**\[16\]** OpenVINO, *Supported Devices*. Official docs ([https\://docs.openvino.ai/2025/documentation/compatibility-and-support/supported-devices.html](https://docs.openvino.ai/2025/documentation/compatibility-and-support/supported-devices.html))

**\[17\]** NVIDIA, *DeepStream SDK*. Official docs ([https\://developer.nvidia.com/deepstream-sdk](https://developer.nvidia.com/deepstream-sdk))

## **B.4. Bảo mật IoT**

**\[18\]** NIST (2022), *NISTIR 8425: Profile of the IoT Core Baseline for Consumer IoT Products*. Publication ([https\://csrc.nist.gov/pubs/ir/8425/final](https://csrc.nist.gov/pubs/ir/8425/final))

**\[19\]** NIST, *NISTIR 8259 Series — Cybersecurity Guidance for IoT*. Official page ([https\://www\.nist.gov/itl/applied-cybersecurity/nist-cybersecurity-iot-program/nistir-8259-series](https://www.nist.gov/itl/applied-cybersecurity/nist-cybersecurity-iot-program/nistir-8259-series))

---

## **B.5. Benchmark và danh mục nền tảng phần cứng**

\[20\] MLCommons, MLPerf Inference: Edge benchmark and results. [https\://mlcommons.org/benchmarks/inference-edge/](https://mlcommons.org/benchmarks/inference-edge/)

\[21\] MLCommons, MLPerf Inference: Tiny benchmark and results. [https\://mlcommons.org/benchmarks/inference-tiny/](https://mlcommons.org/benchmarks/inference-tiny/)

\[22\] Intel, OpenVINO Model Hub — AI inference benchmarks. [https\://www\.intel.com/content/www/us/en/developer/tools/openvino-toolkit/model-hub.html](https://www.intel.com/content/www/us/en/developer/tools/openvino-toolkit/model-hub.html)

\[23\] EEMBC, IoTMark benchmark suite and scores. [https\://www\.eembc.org/iotmark/](https://www.eembc.org/iotmark/)

\[24\] Raspberry Pi, AI HATs documentation. [https\://www\.raspberrypi.com/documentation/accessories/ai-hat-plus.html](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html)

\[25\] NVIDIA, Jetson modules lineup and specifications. [https\://developer.nvidia.com/embedded/jetson-modules/](https://developer.nvidia.com/embedded/jetson-modules/)

\[26\] Texas Instruments, AM69A product page. [https\://www\.ti.com/product/AM69A](https://www.ti.com/product/AM69A)

\[27\] AMD, Ryzen Embedded 8000 Series. [https\://www\.amd.com/en/products/embedded/ryzen/ryzen-8000-series.html](https://www.amd.com/en/products/embedded/ryzen/ryzen-8000-series.html)

# **Phụ lục C — Danh sách phần cứng và phương pháp benchmark**

Phụ lục này giữ danh sách nền tảng đã được sàng lọc để có thể quay lại đối chiếu khi lựa chọn cấu hình. Phần nội dung chính chỉ nêu cấu hình đầu tư đề xuất theo từng giai đoạn; benchmark được xem là bằng chứng theo đúng workload, không phải bảng xếp hạng chung.

## **C.1. Danh sách nền tảng/SoC/Gateway đáng khảo sát**

| Nền tảng/ứng viên | Thông số/đặc điểm đáng chú ý | Vai trò có thể khảo sát | Điểm cần kiểm tra | Benchmark/tài liệu đáng tin cậy |
| :---- | :---- | :---- | :---- | :---- |
| Laptop/workstation hiện có | CPU/GPU hiện có; RAM/SSD tùy máy | Model thử nghiệm, replay dữ liệu, benchmark ban đầu | Chi phí tăng thêm thấp; không đại diện chính xác cho công suất/thermal thiết bị biên. | Benchmark chuẩn riêng của máy chưa xác định; đo workload PoC. |
| Mini PC x86 Intel N100/N97 hoặc CPU tương đương | CPU x86; iGPU; RAM/SSD; có thể có 2.5GbE tùy model | Gateway LAN, API/MQTT, DB, logging, policy; model CPU nhẹ | Dễ triển khai Linux/Docker và nhiều service; cần kiểm tra công suất idle, khả năng tản nhiệt, số NIC/USB và hỗ trợ accelerator. |  |
| Mini PC Intel Core Ultra (các thế hệ có NPU) | CPU \+ iGPU \+ NPU; hiệu năng tùy SKU | Gateway nhiều service và AI nhẹ-vừa; OpenVINO | NPU TOPS và khả năng chạy model thay đổi theo thế hệ/SKU; phải đối chiếu benchmark đúng model và runtime. | Intel OpenVINO Model Hub có kết quả theo model, SKU, precision và CPU/GPU/NPU: [OpenVINO™ Model Hub for AI Inference Benchmarks](https://www.intel.com/content/www/us/en/developer/tools/openvino-toolkit/model-hub.html) |
| AMD Ryzen Embedded 8000 Series | NPU AMD XDNA tối đa 16 TOPS; toàn SoC được AMD nêu tối đa 39 TOPS | Gateway nhúng/industrial PC, vision và automation | Dành cho thiết kế nhúng; board/module, giá và vòng đời tùy nhà cung cấp. | Nguồn thông số chính thức: [AMD Ryzen™ Embedded 8000 Series](https://www.amd.com/en/products/embedded/ryzen/ryzen-8000-series.html) |
| Raspberry Pi 5 | CPU Arm; RAM dùng chung với hệ thống; PCIe qua connector | Gateway PoC, event processing, API/MQTT, camera pipeline nhẹ | Không có NPU tích hợp; hiệu năng vision phụ thuộc model và accelerator. Cần nguồn, tản nhiệt và storage phù hợp. |  |
| Raspberry Pi 5 \+ AI HAT+ 26 TOPS | Hailo-8, 26 TOPS INT8; dùng RAM hệ thống Pi | Vision inference nhiều hơn/nhẹ hơn nhiều luồng tùy model | Không so trực tiếp TOPS INT8 với accelerator INT4/FP16; phải benchmark pipeline đầy đủ. | Thông số chính thức; benchmark độc lập tương đương:  |
| Raspberry Pi 5 \+ AI HAT+ 2 | Hailo-10H, 40 TOPS INT4, RAM riêng 8 GB theo tài liệu Raspberry Pi | Vision và một số workload LLM/VLM cục bộ được hỗ trợ | Khác AI HAT+ thường; không được mặc định model LLM/VLM bất kỳ đều chạy được. | Thông số chính thức; benchmark cùng model trên nền tảng khác:  |
| NVIDIA Jetson Orin Nano Super Developer Kit | NVIDIA công bố tối đa 67 TOPS; công suất cấu hình 7–25 W | Vision AI, nhiều pipeline camera vừa/khá nặng, TensorRT/DeepStream | Giá, công suất, nhiệt, yêu cầu tối ưu TensorRT; kiểm tra hiệu năng sustained chứ không chỉ peak. | Nguồn thông số: [Jetson Modules, Support, Ecosystem, and Lineup \| NVIDIA Developer](https://developer.nvidia.com/embedded/jetson-modules/) ; MLPerf Edge có kết quả theo cấu hình nếu đúng hệ thống/workload: [Benchmark MLPerf Inference: Edge \| MLCommons V6.1 Results](https://mlcommons.org/benchmarks/inference-edge/) |
| NVIDIA Jetson Orin NX | Dòng module đến 157 TOPS tùy cấu hình | Gateway/AI box nhiều camera hoặc pipeline nặng | Chi phí và thiết kế carrier/tản nhiệt cao hơn; chọn đúng SKU 8/16 GB và power mode. | MLPerf Edge: [Benchmark MLPerf Inference: Edge \| MLCommons V6.1 Results](https://mlcommons.org/benchmarks/inference-edge/) ; kết quả phù hợp SKU/workload cần xác minh. |
| NVIDIA Jetson AGX Orin | Dòng hiệu năng cao hơn Orin NX; cấu hình bộ nhớ/compute tùy SKU | AI box nhiều camera, vision phức tạp, robot/industrial edge | Có thể quá mức cho PoC một phòng; điện năng, nhiệt và chi phí lớn hơn. | MLPerf Edge: [Benchmark MLPerf Inference: Edge \| MLCommons V6.1 Results](https://mlcommons.org/benchmarks/inference-edge/) ; số benchmark tương ứng với SKU/workload cần xác minh. |
| Texas Instruments AM69A | Vision SoC; tối đa 32 TOPS từ các deep-learning accelerator; thiết kế hướng 1–12 camera | AI box/vision gateway nhiều camera, edge analytics | Phân khúc embedded/industrial; board phát triển và SDK có độ phức tạp cao hơn SBC phổ thông. | Thông số chính thức: https\://www\.ti.com/product/AM69A ; benchmark cùng model/camera count:  |
| Google Coral Edge TPU | 4 TOPS; Google công bố hiệu suất năng lượng 2 TOPS/W cho accelerator | Inference vision/ML đã lượng tử hóa, node camera/host gọn | Chỉ hỗ trợ model và toán tử tương thích Edge TPU; phụ thuộc host CPU/USB và compiler. | Benchmark độ trễ theo model chính thức: [Edge TPU performance benchmarks \| Coral](https://www.coral.withgoogle.com/docs/edgetpu/benchmarks/) |
| Hailo-8/Hailo-8L module | Accelerator NPU; Hailo-8L 13 TOPS và Hailo-8 26 TOPS theo các sản phẩm liên quan | Bổ sung vision inference cho host tương thích | Cần host PCIe/M.2/adapter tương thích, driver/runtime và nguồn/tản nhiệt phù hợp. |  |
| Sipeed MaixCAM / Kendryte K230 family | Camera/node AI nhúng; thông số và NPU tùy model/board | Phân tán vision AI tại camera hoặc node riêng | Tài nguyên và SDK nhỏ hơn Linux SBC; xác minh model, camera interface, networking và khả năng gửi event ra Gateway. |  |
| STM32N6 | NPU tích hợp 600 GOPS (0.6 TOPS) theo tài liệu ST | Thiết bị nhúng vision/AI low-power, custom camera node | Không phải gateway Linux đa dịch vụ; giới hạn RAM, model, toolchain và tích hợp firmware. | Nguồn chính thức: [STM32N6 series \- STMicroelectronics](https://www.st.com/en/microcontrollers-microprocessors/stm32n6-series.html) ; MLPerf Tiny có thể tham khảo cho workload tiny nếu submission phù hợp: [Benchmark MLPerf Inference: Tiny \| MLCommons V1.1 Results](https://mlcommons.org/benchmarks/inference-tiny/) |
| ESP32-S3 | MCU có vector instructions; không phải NPU vision đa dụng | Wake-word, audio classifier, sensor features và TinyML | RAM/flash, operator và latency giới hạn; phù hợp node chuyên biệt hơn gateway. | MLPerf Tiny kết quả theo submission: [Benchmark MLPerf Inference: Tiny \| MLCommons V1.1 Results](https://mlcommons.org/benchmarks/inference-tiny/) ; benchmark đúng board/model cần xác minh. |

## **C.2. Benchmark: nguồn, phạm vi và cách sử dụng**

| Nguồn benchmark/tài liệu | Đo hoặc công bố gì | Cách diễn giải | Liên kết |
| :---- | :---- | :---- | :---- |
| MLPerf Inference: Edge — MLCommons | Edge inference; workload/dataset/quality target và scenario chuẩn hóa; có kết quả và raw results | Nguồn ưu tiên cho nền tảng edge có submission tương ứng. Chọn đúng system, model, scenario, precision và version. | [Benchmark MLPerf Inference: Edge \| MLCommons V6.1 Results](https://mlcommons.org/benchmarks/inference-edge/) |
| MLPerf Tiny — MLCommons | Image classification, person detection, keyword spotting, anomaly detection, streaming wake-word; latency/quality và tùy chọn energy | Phù hợp MCU/TinyML và thiết bị tài nguyên thấp; không đại diện gateway chạy nhiều service. | [Benchmark MLPerf Inference: Tiny \| MLCommons V1.1 Results](https://mlcommons.org/benchmarks/inference-tiny/) |
| Intel OpenVINO Model Hub | Benchmark model trên thiết bị Intel; có throughput/latency, precision và lựa chọn CPU/GPU/NPU tùy tổ hợp được hỗ trợ | Dùng để chọn cấu hình Intel; không so trực tiếp với nền tảng khác nếu model/settings khác. | [OpenVINO™ Model Hub for AI Inference Benchmarks](https://www.intel.com/content/www/us/en/developer/tools/openvino-toolkit/model-hub.html) |
| Google Coral Edge TPU benchmark | Độ trễ inference cho một số model TensorFlow Lite tương thích Edge TPU; có giải thích giới hạn benchmark | Dùng để ước lượng accelerator Coral cho model tương thích; thời gian model không đồng nghĩa latency end-to-end. | [Edge TPU performance benchmarks \| Coral](https://www.coral.withgoogle.com/docs/edgetpu/benchmarks/) |
| Raspberry Pi AI HAT documentation | Thông số Hailo NPU: AI HAT+ 13/26 TOPS INT8; AI HAT+ 2 40 TOPS INT4; mô tả model/workload được hỗ trợ | Nguồn thông số nhà sản xuất, không phải benchmark so sánh độc lập. | [AI HATs \- Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html) |
| NVIDIA Jetson modules documentation | Thông số dòng Orin, power options và tài liệu phần cứng | Nguồn thông số nhà sản xuất; dùng cùng MLPerf hoặc benchmark tự chạy để đánh giá workload. | [Jetson Modules, Support, Ecosystem, and Lineup \| NVIDIA Developer](https://developer.nvidia.com/embedded/jetson-modules/) |
| TI AM69A | Thông số vision SoC và accelerator cho 1–12 camera | Đối chiếu nền tảng multi-camera/industrial; benchmark cùng model và cấu hình camera cần xác minh. | [AM69A data sheet, product information and support \| TI.com](https://www.ti.com/product/AM69A) |

## **C.3. Quy trình benchmark nội bộ cho Smart Home**

Để so sánh các nền tảng theo cùng điều kiện, cố định model, weights, dataset, resolution/FPS, precision, batch size, runtime và phiên bản phần mềm. Ghi riêng kết quả vendor-reported, benchmark độc lập và phép đo nội bộ.

**• Workload A — occupancy sensor-only:** kết hợp PIR/mmWave, lux và trạng thái KNX; dùng làm baseline rule-based và ML nhẹ.

**• Workload B — camera occupancy/person detection:** cùng video test, resolution, FPS và model đã lượng tử hóa phù hợp từng runtime.

**• Workload C — context fusion:** hợp nhất event camera, trạng thái KNX/DALI/CANx và thời gian; đo latency end-to-end chứ không chỉ inference.

**• Workload D — stress/soak:** chạy 8–24 giờ hoặc lâu hơn với các service dự kiến; theo dõi thermal throttling, RAM, storage growth, restart và mất kết nối.

**Các chỉ số cần ghi:** precision/recall/F1 và false actions; inference latency p50/p95/p99; end-to-end event-to-actuator latency; throughput/FPS và số luồng đồng thời; CPU/RAM/NPU utilization; công suất idle/average/peak; nhiệt độ và throttling; dữ liệu media thô truyền qua LAN/WAN; thời gian phục hồi sau lỗi.

[image1]: <data:image/png;base64,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>