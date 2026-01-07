import http from "k6/http";
import { check } from "k6";

export const options = {
    scenarios: {
        traffic: {
            executor: "ramping-arrival-rate",
            timeUnit: "1s",
            preAllocatedVUs: 2000,
            startRate: 20,
            stages: [
                { duration: "20s", target: 10 },
                { duration: "50s", target: 60 },
                { duration: "60s", target: 60 },
                { duration: "10s", target: 30 },
                { duration: "60s", target: 30 },
                { duration: "10s", target: 65 },
                { duration: "60s", target: 65 },
                { duration: "10s", target: 10 },
                { duration: "20s", target: 10 },
            ],
            gracefulStop: "10s",
        },
    },
    thresholds: {
        http_req_duration: ["p(95)<6250", "avg<3000"],
    },
    summaryTrendStats: ["avg", "p(95)"],
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
    const res = http.get(`${BASE_URL}/news.php`);
    check(res, { "news OK": (r) => r.status === 200 });
}
