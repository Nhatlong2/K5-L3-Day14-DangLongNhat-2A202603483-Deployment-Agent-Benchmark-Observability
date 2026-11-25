# Benchmark & Observability Report — Day 14

> Mọi con số dưới đây phải lấy từ report JSON / CSV / screenshot thật chạy trên máy của bạn.

**Họ tên:** Đặng Long Nhật — 2A202603483
**Ngày chạy:** 2026-11-25
**Môi trường:** [Điền cấu hình máy + Docker Desktop CPU/RAM của bạn]

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận phản hồi trong dưới 0,5 giây ở mức tải thông thường, tránh cảm giác chậm trễ |
| Error rate `/ask` | < 2.0 % | Mock LLM có ~1% lỗi upstream tự nhiên; đặt error budget 2% để dung sai nhiễu ngắn nhưng vẫn phát hiện sự cố thật |
| Accuracy trên golden dataset | ≥ 85 % | Đảm bảo chất lượng câu trả lời không bị suy giảm khi thay đổi prompt/KB (mục tiêu sau sửa KB: 100%) |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

> Lấy số liệu từ `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 10 | | | | | | |
| 50 | | | | | | |
| 100 | | | | | | |

**Nhận xét:** RPS tăng nhanh ở các mức concurrency thấp (1 → 10 → 50) vì tác vụ chủ yếu là I/O-bound (chờ `asyncio.sleep` của mock LLM), nhưng không tăng tuyến tính mãi khi lên cao do giới hạn event loop, context switching và tài nguyên CPU/socket của 1 process uvicorn.

### 2.2 Tail latency

> Lấy số liệu từ `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | | | |
| 0.03 (mặc định) | | | |
| 0.1 | | | |

**Nhận xét:** `p99` (và sau đó là `p95` khi tỷ lệ chậm lên 10%) nhạy nhất với các request chậm bất thường, trong khi `avg` chỉ tăng nhẹ vì bị pha loãng bởi đa số request nhanh. Do đó SLO bắt buộc phải đặt theo percentile (`p95`/`p99`) để phản ánh đúng trải nghiệm tệ nhất của người dùng thay vì bị che giấu bởi giá trị trung bình.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

> Lấy số liệu từ `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | | | |
| Avg tokens / câu | | | |
| Tổng cost (USD) | | | |
| Cost / câu đúng (USD) | | | |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung entry tài liệu về Kubernetes HPA vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung entry so sánh JWT và API key vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
Agent v2 thêm bước retrieval (RAG) nên tốn thêm ~20ms latency và nhiều input tokens hơn (tổng chi phí tăng), nhưng độ chính xác tăng vượt trội từ mức rất thấp lên 91,3% (và 100% sau khi bổ sung KB). Nhờ vậy chỉ số **cost / câu đúng** của v2 rẻ hơn nhiều lần so với v1 — minh chứng rằng cần đánh giá chi phí gắn liền với chất lượng chứ không chỉ nhìn chi phí thô mỗi request.

**CI Quality Gate (Exercise 7.3):** Đã cấu hình `.github/workflows/eval.yml` chạy `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85` trên mỗi Pull Request; khi accuracy dưới ngưỡng hoặc có regression, script trả về exit code `1` làm job CI fail và tự động chặn merge.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] `screenshots/grafana-dashboard.png` — Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] `screenshots/jaeger-slow-trace.png` — Một trace chậm trong Jaeger (thấy span chiếm nhiều thời gian nhất)
- [ ] `screenshots/jaeger-error-trace.png` — Một trace lỗi trong Jaeger (có event `exception`)
- [ ] `screenshots/prometheus-alert-firing.png` — Trang Alerts của Prometheus với ít nhất 2 alert đang **firing**

**Trả lời nhanh Exercise 7.4:**
1. *p95 và avg trên Grafana*: `[Điền số p95 và avg bạn quan sát được]` — khoảng cách lớn giữa `avg` và `p95/p99` thể hiện hiện tượng tail latency.
2. *Panel Requests/s theo instance*: Nginx chia tải gần như đều cho các instance theo round-robin.
3. *Vì sao input tokens/s > output tokens/s?* Vì mỗi prompt gửi lên LLM bao gồm system prompt + tài liệu RAG (context) + câu hỏi, dài hơn câu trả lời ngắn gọn mà model sinh ra.
4. *`curl http://localhost:8080/metrics` trả về gì?* Trả về **404 Not Found**, vì Nginx cố tình chặn `/metrics` từ bên ngoài để bảo mật (chỉ Prometheus trong mạng Docker nội bộ mới được scrape).

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | `[Điền thời gian đo thật]` | Error rate (Golden Signals) & LLM calls ok/error |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | `[Điền thời gian đo thật]` | Latency p50/p95/p99 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | `[Điền thời gian đo thật]` | Cost USD/giờ & LLM p95 |
| D | `docker pause` 1 instance | `AgentInstanceDown` | `[Điền thời gian đo thật]` | Instances up & Req/s theo instance |
| E | `AGENT_VERSION=v1` | Không có | N/A | Retrieval hit ratio & bảng Version |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
Alert hạ tầng chỉ theo dõi latency, error rate, uptime và chi phí — không đo được ngữ nghĩa câu trả lời. Để phát hiện sớm suy giảm chất lượng: (1) chạy eval tự động trên golden dataset trong CI/CD trước khi deploy (quality gate); (2) theo dõi các metric nghiệp vụ như `retrieval_hit_ratio` (đặt alert khi tụt mạnh); (3) chạy online evaluation / LLM-as-judge trên mẫu traffic thật và thu thập phản hồi người dùng (thumbs up/down).

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được trong Jaeger:

- `trace_id`: `[Điền trace_id thật từ Jaeger]`
- Tổng thời gian: `[Điền ms]` ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`[Điền ms]` ms, `[Điền %]`%)
- Dòng log tương ứng (grep theo `trace_id` từ `docker compose -p k5-day14-observability logs agent`):

```json
{"DÁN DÒNG LOG JSON THẬT CÓ CÙNG trace_id TẠI ĐÂY": true}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

> Lấy số liệu từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv`.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** `[Đối chiếu số liệu thật]` — Scale từ 1 lên 3 instance giúp giảm áp lực CPU/event loop trên mỗi worker và tăng độ chịu tải, nhưng nếu `p95` gần như không đổi đáng kể thì nút thắt nằm ở **upstream LLM latency** (thời gian chờ model trả lời, thể hiện rõ trên panel LLM latency), không phải ở năng lực xử lý của bản thân web server.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. Không bao giờ chỉ nhìn latency trung bình; SLO phải đặt theo `p95`/`p99` để kiểm soát tail latency.
  2. Ba trụ cột Metrics – Traces – Logs liên kết với nhau qua `trace_id` giúp đi nhanh từ triệu chứng tổng quan xuống nguyên nhân gốc rễ.
  3. Metric hạ tầng xanh không đồng nghĩa chất lượng AI tốt — bắt buộc phải có Eval & Quality Gate trong CI/CD.
- Nếu đưa agent lên production thật, nên bổ sung thêm: alert cho `retrieval_hit_ratio` giảm bất thường, giám sát tỷ lệ lỗi 5xx ở tầng Load Balancer/Ingress (bắt lỗi 504), synthetic monitoring từ bên ngoài, và Alertmanager gửi cảnh báo về Slack/PagerDuty.
