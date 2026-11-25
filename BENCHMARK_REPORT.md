# Benchmark & Observability Report — Day 14

> Mọi con số dưới đây được lấy trực tiếp từ report JSON, CSV và screenshot đo thực tế.

**Họ tên:** Đặng Long Nhật — 2A202603483
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11 + WSL2 (Ubuntu), Docker Desktop 29.9.3

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này | 
| ----- | ----- | ----- | 
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận phản hồi trong dưới 0,5 giây ở mức tải thông thường, tránh cảm giác chậm trễ | 
| Error rate `/ask` | < 2.0 % | Mock LLM có \~1% lỗi upstream tự nhiên; đặt error budget 2% để dung sai nhiễu ngắn nhưng vẫn phát hiện sự cố thật | 
| Accuracy trên golden dataset | ≥ 85 % | Đảm bảo chất lượng câu trả lời không bị suy giảm khi thay đổi prompt/KB (mục tiêu sau sửa KB: 100%) | 

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

*(Số liệu khớp với `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`)*

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO | 
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | 
| 1 | 3.91 | 190.9 | 225.0 | 1695.7 | 0.33% | PASS | 
| 10 | 44.79 | 195.8 | 228.3 | 1707.8 | 1.00% | PASS | 
| 50 | 43.02 | 380.5 | 3849.7 | 5562.0 | 1.33% | FAIL (p95 > 500ms) | 
| 100 | 37.62 | 1334.4 | 5353.5 | 6243.7 | 0.33% | FAIL (p95 > 500ms) | 

**Nhận xét:** RPS tăng mạnh từ concurrency `1` → `10` (`3.91 → 44.79 req/s`) nhưng **không tăng tuyến tính** khi lên `50` và `100` (thậm chí giảm nhẹ xuống `43.02` và `37.62 req/s`), trong khi `p95` vọt từ `228.3 ms` lên `3849.7 ms` và `5353.5 ms`. Nguyên nhân là một process uvicorn đơn lẻ bị bão hoà hàng đợi và chi phí chuyển ngữ cảnh/socket khi quá nhiều request đồng thời cùng chờ xử lý.

### 2.2 Tail latency

*(Số liệu khớp với `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`, `--concurrency 20`, `--requests 300`)*

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) | 
| ----- | ----- | ----- | ----- | 
| 0 | 221.6 | 312.8 | 457.9 | 
| 0.03 (mặc định) | 261.5 | 293.2 | 1707.1 | 
| 0.1 | 327.5 | 1691.1 | 1777.0 | 

**Nhận xét:** `p99` (ở mức 3% slow đã nhảy từ `457.9 ms` lên `1707.1 ms`) và `p95` (ở mức 10% slow nhảy từ `293.2 ms` lên `1691.1 ms`) nhạy nhất với các request chậm bất thường, trong khi `avg` chỉ tăng nhẹ từ `221.6 ms` lên `327.5 ms` vì bị pha loãng bởi đa số request nhanh. Do đó SLO bắt buộc phải đặt theo percentile (`p95`/`p99`) thay vì giá trị trung bình.

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

*(Số liệu khớp với `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`)*

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) | 
| ----- | ----- | ----- | ----- | 
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) | 
| Avg tokens / câu | 56.7 | 108.8 | 113.7 | 
| Tổng cost (USD) | \$0.000398 | \$0.000758 | \$0.000790 | 
| Cost / câu đúng (USD) | \$0.00039795 | \$0.00003607 | \$0.00003436 | 
| Quality gate | FAIL | PASS | PASS | 

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì | 
| ----- | ----- | ----- | 
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung entry tài liệu về Kubernetes HPA (Horizontal Pod Autoscaler) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` | 
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung entry so sánh JWT và API key vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` | 

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
Agent v2 thêm bước retrieval (RAG) nên latency p95 tăng nhẹ (`186.5 → 212.5 ms`) và lượng token trung bình tăng gần gấp đôi (`56.7 → 113.7 tokens/câu`), làm tổng chi phí tăng từ `$0.000398` lên `$0.000790`. Tuy nhiên độ chính xác tăng vượt trội từ `4.3%` lên `91.3%` (và `100.0%` sau sửa KB, 0 regression), giúp **cost / câu đúng** giảm hơn **11 lần** (`$0.00039795` → `$0.00003436`).

**CI Quality Gate (Exercise 7.3):** Đã tạo `.github/workflows/eval.yml` chạy `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85` trên mỗi Pull Request; khi accuracy dưới ngưỡng hoặc có regression, script trả về exit code `1` làm job CI fail và chặn merge tự động.

## 4. Observability stack (production)

### 4.1 Screenshot

* \[x\] `screenshots/grafana-dashboard.png` — Dashboard Grafana khi đang có tải (30 users: Traffic `18.4 req/s`, Error rate `1.09%`, Latency p95 `292.55 ms`, In-flight `4`, Instances up `2`, LLM cost 1h `$0.7960`)

* \[x\] `screenshots/jaeger-slow-trace.png` — Trace chậm `231a49a8bb98208b09cb161c31a6bf67` trong Jaeger (tổng `1.7s`, span `chat mock-llm-small` chiếm \~98.5%)

* \[x\] `screenshots/jaeger-error-trace.png` — Trace lỗi `96e98b9a14e458e5d43945f8449e41ab` (HTTP 503, có event `exception`: `Upstream LLM error: 503 Service Unavailable (mock)`)

* \[x\] `screenshots/prometheus-alert-firing.png` — Trang Alerts của Prometheus hiển thị 2 alert cùng đang **FIRING** (`LLMCostBurnRateHigh` = `$8.62/giờ` và `AgentHighErrorRate`)

**Trả lời Exercise 7.4:**

1. *p95 và avg trên Grafana*: Latency p95 đạt **292.55 ms** (còn p99 đạt \~1.7–1.8s, avg \~250 ms) — khoảng cách lớn giữa `avg` và `p99` thể hiện rõ hiện tượng tail latency (\~3% request chậm bất thường).

2. *Panel Requests/s theo instance*: Hai đường của 2 container `agent` gần như chồng khớp nhau (\~9.2 req/s mỗi instance), chứng tỏ Nginx chia đều tải theo round-robin.

3. *Vì sao input tokens/s lớn hơn output tokens/s?* Vì prompt gửi lên LLM bao gồm system prompt + ngữ cảnh RAG (context) + câu hỏi người dùng, dài hơn câu trả lời ngắn gọn mà model trả về.

4. *`curl http://localhost:8080/metrics` trả về gì?* Trả về **404 Not Found**, vì Nginx chặn truy cập `/metrics` từ bên ngoài để bảo mật; chỉ Prometheus trong mạng Docker nội bộ mới được scrape trực tiếp container `agent`.

### 4.2 Thí nghiệm "phá hệ thống"

| \# | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất | 
| ----- | ----- | ----- | ----- | ----- | 
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | \~1 phút 30 giây (`for: 1m` + cửa sổ đánh giá) | Error rate (Golden Signals) & LLM calls ok/error | 
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | \~2 phút (`for: 2m`, burn rate đạt `$8.62/giờ > $2/giờ`) | Cost burn rate (USD/giờ) & LLM latency p95 | 
| E | `AGENT_VERSION=v1` | Không có | N/A | Retrieval hit ratio tụt về 0% & bảng Phiên bản đang chạy | 

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
Alert hạ tầng chỉ theo dõi latency, error rate, uptime và chi phí — không phát hiện được câu trả lời sai ngữ nghĩa. Trong production cần kết hợp: (1) chạy eval tự động trên golden dataset trong CI/CD trước khi deploy (quality gate); (2) theo dõi và đặt alert cho các metric nghiệp vụ như `retrieval_hit_ratio` khi tụt mạnh; (3) online evaluation / LLM-as-judge trên mẫu traffic thật kết hợp phản hồi người dùng.

### 4.3 Debug bằng trace

Trace chậm nhất chọn từ Jaeger:

* `trace_id`: `231a49a8bb98208b09cb161c31a6bf67`

* Tổng thời gian: `1679.7 ms` (hiển thị `1.7s` trên Jaeger)

* Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1654.3 ms`, chiếm **98.5%** tổng thời gian; bước `agent.retrieve_context` chỉ mất `24.3 ms`)

* Dòng log JSON tương ứng (grep từ `docker compose -p k5-day14-observability logs agent | grep 231a49a8bb98208b09cb161c31a6bf67`):

```
{"ts": "2026-11-25T09:55:01.847470+00:00", "level": "INFO", "service": "observable-agent", "instance": "e8d3b6dde8bb", "event": "llm_call", "trace_id": "231a49a8bb98208b09cb161c31a6bf67", "span_id": "01e02e765c41f9ba", "request_id": "3514114d47ae", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1654.3}

```

```
{"ts": "2026-11-25T09:55:01.847939+00:00", "level": "INFO", "service": "observable-agent", "instance": "e8d3b6dde8bb", "event": "http_request", "trace_id": "231a49a8bb98208b09cb161c31a6bf67", "span_id": "01e02e765c41f9ba", "request_id": "3514114d47ae", "method": "POST", "route": "/ask", "status": 200, "ms": 1679.7}

```

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

*(Số liệu hàng `Aggregated` khớp với `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv`)*

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 1 | 65.49 | 200 | 450 | 1700 | 72 / 7778 (0.93%) | 
| 3 | 66.06 | 190 | 230 | 1700 | 67 / 7843 (0.85%) | 

*(Riêng endpoint `POST /ask`: 1 instance đạt 59.79 RPS, p95 = **480 ms**, p99 = 1700 ms; 3 instances đạt 59.86 RPS, p95 = **230 ms**, p99 = 1700 ms.)*

**Giải thích kết quả:** Scale từ 1 lên 3 instance cải thiện rõ rệt **p95** (giảm gần một nửa từ `450 ms → 230 ms`, riêng `/ask` giảm từ `480 ms → 230 ms`) vì mỗi container chỉ được cấp giới hạn `0.5 CPU` nên 3 instance giúp san tải xử lý HTTP/tracing/retrieval và loại bỏ hàng đợi nội bộ. Tuy nhiên **p99 vẫn giữ nguyên ở `1700 ms`** và tổng RPS chỉ tăng nhẹ (`65.49 → 66.06 req/s`) vì nút thắt ở đuôi phân phối nằm ở **upstream LLM tail latency** (`MOCK_SLOW_RATE=3%`, cộng thêm 1500 ms) và thời gian nghỉ (`wait_time`) của 100 user ảo trên Locust — scale số web instance không thể rút ngắn thời gian chờ phản hồi từ LLM upstream.

## 6. Kết luận

* 3 điều học được về benchmark & observability:

  1. Không bao giờ chỉ nhìn latency trung bình; SLO phải đặt theo `p95`/`p99` để phản ánh đúng tail latency mà người dùng cuối trải nghiệm.

  2. Ba trụ cột Metrics – Traces – Logs liên kết chặt chẽ qua `trace_id` giúp đi nhanh từ tín hiệu tổng quan (Grafana/Prometheus) tới đúng span gây chậm (Jaeger) và chi tiết sự kiện (JSON log).

  3. Metric hạ tầng xanh không bảo đảm chất lượng AI tốt — bắt buộc phải có Eval trên golden dataset và Quality Gate tự động trong CI/CD.

* Nếu đưa agent lên production thật, cần bổ sung thêm: alert cho `retrieval_hit_ratio` tụt bất thường, giám sát tỷ lệ lỗi 5xx ở tầng Load Balancer/Nginx (bắt lỗi 504), synthetic monitoring từ bên ngoài, và Alertmanager gửi cảnh báo về Slack/PagerDuty.