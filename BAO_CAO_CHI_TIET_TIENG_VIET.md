# BÁAO CÁO CHI TIẾT VỀ PHÂN TÍCH TỰ ĐỘNG SCALING (Autoscaling Analysis)

**Ngày tạo**: 23/01/2026  
**Dự án**: Autoscaling Analysis - Phân tích các chiến lược tự động mở rộng hạ tầng

---

## MỤC LỤC
1. [Giới thiệu](#giới-thiệu)
2. [Các khái niệm cơ bản](#các-khái-niệm-cơ-bản)
3. [Các chính sách scaling](#các-chính-sách-scaling)
4. [Phân tích chi tiết](#phân-tích-chi-tiết)
5. [Các metrics và ý nghĩa](#các-metrics-và-ý-nghĩa)
6. [Phát hiện bất thường](#phát-hiện-bất-thường)
7. [Kết luận và khuyến nghị](#kết-luận-và-khuyến-nghị)

---

## Giới thiệu

Dự án này giải quyết một bài toán quan trọng trong quản lý hạ tầng cloud: **Làm sao để tự động điều chỉnh số lượng máy chủ sao cho vừa đủ xử lý tải công việc mà không lãng phí tài nguyên?**

Trong một hệ thống web hoặc ứng dụng cloud:
- **Vào giờ cao điểm** (peak hours): Người dùng tăng đột ngột, hệ thống cần thêm máy chủ để xử lý
- **Vào giờ thấp điểm** (off-peak): Người dùng ít, có thể rút bớt máy chủ để tiết kiệm chi phí

Tự động scaling giúp hệ thống tự động điều chỉnh tài nguyên mà không cần can thiệp thủ công.

---

## Các khái niệm cơ bản

### 1. **Tải công việc (Load / Requests)**
- Là số lượng yêu cầu (requests) mà hệ thống nhận được trong một khoảng thời gian
- Được đo bằng: số requests/phút, số requests/giây
- Ví dụ: Vào lúc 10:00 sáng, hệ thống nhận 5000 requests/phút

### 2. **Máy chủ (Server)**
- Một máy tính được sử dụng để xử lý các yêu cầu của người dùng
- Mỗi máy chủ có khả năng xử lý một lượng tải nhất định (ví dụ: 1000 requests/phút)
- Nhiều máy chủ hơn = Khả năng xử lý tải lớn hơn

### 3. **Scale Out (Mở rộng ra)**
- Tăng số lượng máy chủ
- Sử dụng khi tải tăng lên quá cao
- Ví dụ: Từ 2 máy chủ lên 3 máy chủ

### 4. **Scale In (Thu gọn lại)**
- Giảm số lượng máy chủ
- Sử dụng khi tải giảm xuống
- Ví dụ: Từ 3 máy chủ xuống 2 máy chủ

### 5. **Chi phí (Cost)**
- Mỗi máy chủ có chi phí chạy (ví dụ: 0.10 USD/giờ)
- Tổng chi phí = Số máy chủ trung bình × Chi phí/giờ × Thời gian
- Mục tiêu: Giảm chi phí mà vẫn đảm bảo hiệu năng

### 6. **Threshold (Ngưỡng)**
- **Scale-out threshold**: Mức tải mà khi vượt quá thì phải thêm máy chủ (ví dụ: 75%)
- **Scale-in threshold**: Mức tải dưới đó thì có thể rút bớt máy chủ (ví dụ: 30%)
- Được tính theo % công suất của máy chủ

---

## Các chính sách Scaling

Dự án này so sánh 3 chính sách scaling khác nhau:

### 1. **Threshold Scaling (Scaling dựa trên Ngưỡng)**

#### Nguyên lý:
- Là chính sách **đơn giản nhất**
- Chỉ nhìn vào tải **hiện tại**
- Không dự đoán tương lai

#### Luật quyết định:
```
Nếu tải hiện tại > 75% → Scale OUT (thêm máy chủ)
Nếu tải hiện tại < 30% → Scale IN (rút bớt máy chủ)
Ngược lại → Không làm gì cả (NO ACTION)
```

#### Ưu điểm:
- ✅ Dễ hiểu, dễ triển khai
- ✅ Phản ứng nhanh với sự thay đổi tải
- ✅ Không cần dữ liệu lịch sử phức tạp

#### Nhược điểm:
- ❌ Có thể **quá linh cảm** - Scale quá nhanh khi tải dao động
- ❌ Không dự đoán trước, nên khi tải tăng đột ngột, hệ thống có thể chậm
- ❌ Chi phí có thể cao do scaling quá nhiều lần

#### Ví dụ:
```
Thời gian    Tải hiện tại    Hành động
10:00        50% (< 75%)     → Không làm gì
10:05        80% (> 75%)     → SCALE OUT (thêm máy)
10:10        70% (75% - 30%) → Không làm gì
10:15        25% (< 30%)     → SCALE IN (rút bớt máy)
```

---

### 2. **Predictive Scaling (Scaling dựa trên Dự đoán)**

#### Nguyên lý:
- Là chính sách **thông minh hơn**
- Nhìn vào tải **dự đoán trong tương lai** (không chỉ hiện tại)
- Dự đoán bằng cách xem 5 thời điểm tiếp theo

#### Luật quyết định:
```
Nếu trong 5 thời điểm tiếp theo, 
   ≥ 5 lần tải vượt quá 75% 
   → Scale OUT (thêm máy sớm hơn)

Nếu trong 5 thời điểm tiếp theo, 
   ≥ 5 lần tải dưới 30% 
   → Scale IN (rút máy sớm hơn)

Ngược lại → Không làm gì cả
```

#### Ưu điểm:
- ✅ **Dự đoán trước** được tăng tải → Thêm máy **trước khi bị chậm**
- ✅ Giảm được số lần scaling không cần thiết
- ✅ Cải thiện trải nghiệm người dùng
- ✅ Có thể tiết kiệm chi phí hơn Threshold Scaling

#### Nhược điểm:
- ❌ Dữ liệu dự đoán có thể **không chính xác**
- ❌ Phức tạp hơn, cần thuật toán dự báo tốt
- ❌ Nếu dự đoán sai, có thể scale không đúng lúc

#### Ví dụ:
```
Thời gian    Tải hiện tại    Tải dự đoán (5 bước tới)    Hành động
10:00        50%             55%, 60%, 65%, 70%, 75%     → Không làm gì
10:05        60%             78%, 80%, 82%, 85%, 87%     → SCALE OUT (dự đoán sẽ cao)
10:10        80%             82%, 80%, 75%, 70%, 65%     → Giữ nguyên
10:15        70%             20%, 22%, 25%, 28%, 30%     → Không làm gì
10:20        25%             10%, 12%, 15%, 18%, 20%     → SCALE IN (dự đoán sẽ thấp)
```

---

### 3. **Hysteresis Scaling (Scaling với Thời gian chờ)**

#### Nguyên lý:
- Cải tiến của Threshold Scaling
- Thêm một **"thời gian chờ" (cooldown)**
- Ngăn chặn **scaling quá nhanh** (flapping)

#### Luật quyết định:
```
Nếu vừa scale trong 10 thời điểm gần đây
   → KHÔNG ĐƯỢC SCALE LẠI (chờ 10 bước)
   (điều này gọi là "cooldown period")

Ngược lại, áp dụng quy tắc Threshold Scaling
```

#### Ưu điểm:
- ✅ Ổn định hơn, ít **flapping** (tình trạng scale lên rồi scale xuống liên tục)
- ✅ Giảm được overhead của việc scale
- ✅ Dễ triển khai hơn Predictive Scaling
- ✅ Chi phí có thể thấp hơn vì ít scaling

#### Nhược điểm:
- ❌ Nếu cooldown quá dài, có thể **phản ứng chậm** với sự thay đổi đột ngột
- ❌ Vẫn không dự đoán trước như Predictive Scaling

#### Ví dụ:
```
Thời gian    Tải        Hành động              Cooldown còn lại
10:00        50%        Không làm gì           0
10:05        80%        SCALE OUT (thêm máy)   10 (đặt lại)
10:10        85%        KHÔNG ĐƯỢC SCALE       9
10:15        90%        KHÔNG ĐƯỢC SCALE       8
10:20        95%        KHÔNG ĐƯỢC SCALE       7
10:25        70%        KHÔNG ĐƯỢC SCALE       6
10:30        25%        KHÔNG ĐƯỢC SCALE       5
10:35        20%        KHÔNG ĐƯỢC SCALE       4
10:40        15%        KHÔNG ĐƯỢC SCALE       3
10:45        10%        KHÔNG ĐƯỢC SCALE       2
10:50        10%        KHÔNG ĐƯỢC SCALE       1
10:55        10%        SCALE IN (rút máy)     10 (đặt lại)
```

---

## Phân tích chi tiết

### So sánh 3 Chính sách

| Tiêu chỉ | Threshold | Predictive | Hysteresis |
|----------|-----------|-----------|-----------|
| **Độ phức tạp** | Đơn giản | Phức tạp | Trung bình |
| **Tốc độ phản ứng** | Nhanh | Nhanh nhất | Chậm hơn |
| **Số lần scaling** | Nhiều | Ít | Ít nhất |
| **Chi phí** | Cao | Thấp nhất | Thấp |
| **Tính ổn định** | Kém | Tốt | Tốt nhất |
| **Dễ triển khai** | Rất dễ | Khó | Dễ |
| **Yêu cầu dữ liệu** | Ít | Nhiều | Ít |

---

## Các Metrics và ý nghĩa

Khi chạy phân tích, bạn sẽ thấy các chỉ số sau:

### 1. **Total Cost (Tổng chi phí)**
- **Ý nghĩa**: Tổng chi phí chạy hệ thống trong thời gian phân tích
- **Công thức**: Tổng (Số máy chủ mỗi phút × Chi phí/giờ)
- **Ví dụ**: $50.00 có nghĩa là chạy hệ thống mất 50 đô la
- **Mục tiêu**: Càng thấp càng tốt ✓

### 2. **Average Servers (Số máy chủ trung bình)**
- **Ý nghĩa**: Trung bình dùng bao nhiêu máy chủ trong suốt thời gian
- **Công thức**: Tổng (Số máy ở mỗi thời điểm) / Số thời điểm
- **Ví dụ**: 2.5 có nghĩa là trung bình dùng 2.5 máy (đôi khi 2, đôi khi 3)
- **Giải thích**: Thấp hơn = Hiệu quả sử dụng tài nguyên tốt hơn

### 3. **Scaling Events (Số lần scaling)**
- **Ý nghĩa**: Bao nhiêu lần hệ thống scale up hoặc scale down
- **Ví dụ**: 50 lần có nghĩa là trong 24 giờ, đã scale lên/xuống 50 lần
- **Tại sao quan trọng**: 
  - Mỗi lần scale có chi phí overhead (downtime, cài đặt máy...)
  - Scaling quá nhiều = Lãng phí tài nguyên
  - Scaling quá ít = Có thể không đủ tài nguyên
- **Mục tiêu**: Số lần vừa phải, không quá nhiều ✓

### 4. **Cost Per Hour (Chi phí/giờ)**
- **Ý nghĩa**: Trung bình chi phí per 1 giờ
- **Công thức**: Tổng chi phí / Tổng giờ
- **Ví dụ**: $2.50/giờ
- **Dùng để**: So sánh chi phí giữa các chính sách

---

## Phát hiện bất thường (Anomaly Detection)

### Tại sao cần phát hiện bất thường?
- Tải bình thường theo quy luật hàng ngày (cao buổi sáng, thấp vào đêm)
- **Đột ngột** có một ngày tải tăng gấp đôi → Có vấn đề!
  - Có thể là **tấn công DDoS** (hacker)
  - Có thể là **lỗi trong code** (vòng lặp vô hạn)
  - Có thể là **sự kiện đặc biệt** (sale, promotion)

### 2 Phương pháp phát hiện:

#### **A. Spike Detection (Phát hiện tăng đột ngột)**
- **Nguyên lý**: So sánh tải hiện tại với giá trị trung bình của vài phút trước
- **Công thức**: 
  ```
  Nếu |Tải hiện tại - Trung bình| > Ngưỡng × Độ lệch chuẩn
  → Đây là bất thường (spike)
  ```
- **Ví dụ với Ngưỡng = 2.0**:
  ```
  Tải trung bình 10 phút: 5000 requests
  Độ lệch chuẩn: 500 requests
  Ngưỡng: 5000 + 2.0 × 500 = 6000
  
  Nếu tải hiện tại = 7000 → PHÁT HIỆN SPIKE
  Nếu tải hiện tại = 5200 → Bình thường
  ```
- **Ứng dụng**: Phát hiện tăng tải không bình thường

#### **B. DDoS Detection (Phát hiện tấn công DDoS)**
- **Nguyên lý**: DDoS = Tải cao + Tỷ lệ lỗi cao
- **Công thức**:
  ```
  Nếu (Tải > 10000) VÀ (Tỷ lệ lỗi > 30%)
  → Là DDoS (phần lớn)
  ```
- **Ví dụ**:
  ```
  Tải = 8000, Tỷ lệ lỗi = 35% → Bình thường (tải không cao)
  Tải = 15000, Tỷ lệ lỗi = 35% → Có thể DDoS ⚠️
  Tải = 12000, Tỷ lệ lỗi = 5% → Bình thường (lỗi ít)
  ```
- **Ứng dụng**: Cảnh báo khi bị tấn công

---

## Kết luận và Khuyến nghị

### Kết luận

1. **Không có chính sách "hoàn hảo"** - Mỗi chính sách có ưu nhược điểm
2. **Lựa chọn phụ thuộc vào yêu cầu**:
   - Chi phí là ưu tiên → **Predictive Scaling** (chi phí thấp nhất)
   - Ổn định là ưu tiên → **Hysteresis Scaling** (flapping ít nhất)
   - Đơn giản là ưu tiên → **Threshold Scaling** (dễ triển khai)

### Khuyến nghị cho các tình huống khác nhau

#### **Tình huống 1: E-commerce lớn (ví dụ Shopee, Lazada)**
- **Chọn**: Predictive Scaling hoặc kết hợp cả ba
- **Lý do**: Tải có quy luật rõ ràng (cao vào lúc bán), cần dự đoán trước
- **Thêm**: Phát hiện DDoS vì thường bị tấn công

#### **Tình huống 2: Blog, Website thông tin**
- **Chọn**: Threshold Scaling + Hysteresis Scaling
- **Lý do**: Tải ổn định, không cần dự đoán phức tạp

#### **Tình huống 3: Ứng dụng gaming, live streaming**
- **Chọn**: Hysteresis Scaling
- **Lý do**: Tải có thể dao động nhanh, cần ổn định, tránh flapping

#### **Tình huống 4: API service của startup**
- **Chọn**: Threshold Scaling
- **Lý do**: Chi phí ít, không cần phức tạp, dễ bảo trì

---

## Hướng dẫn sử dụng Dashboard

### Để chạy phân tích:
1. Vào tab **"⚙️ Autoscaling"**
2. Điều chỉnh các tham số:
   - **Scale-out threshold**: Ngưỡng thêm máy (mặc định 0.75 = 75%)
   - **Scale-in threshold**: Ngưỡng rút máy (mặc định 0.30 = 30%)
3. Click **"📊 Analyze Scaling Policies"**
4. Xem kết quả so sánh

### Để phát hiện bất thường:
1. Vào tab **"🚨 Anomalies"**
2. Chọn:
   - **Spike Detection**: Phát hiện tăng đột ngột
   - **DDoS Detection**: Phát hiện tấn công
3. Điều chỉnh ngưỡng
4. Click **"🚨 Detect Anomalies"**

---

## Tài liệu tham khảo

- **Tệp dự báo**: `src/forecasters.py`
- **Tệp scaling policies**: `src/autoscaling.py`
- **Dashboard**: `dashboard.py`
- **Huấn luyện mô hình**: `train.py`

---

**Tác giả**: Autoscaling Analysis Project  
**Phiên bản**: 1.0  
**Cập nhật lần cuối**: 23/01/2026
