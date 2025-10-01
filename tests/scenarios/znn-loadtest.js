import http from "k6/http";
import { check } from "k6";

export const options = {
    scenarios: {
        traffic: {
            executor: 'ramping-arrival-rate',
            timeUnit: '1s',
            startRate: 100,
            preAllocatedVUs: 200,
            maxVUs: 2500,
            stages: [
                { duration: '15s', target:  40 },
                { duration: '60s', target:  40 },
                { duration: '30s', target:  85 },
                { duration: '60s', target:  85 },
                { duration:  '5s', target:  40 },
                { duration: '60s', target:  40 },
                { duration:  '5s', target:  80 },
                { duration: '30s', target:  80 },
                { duration:  '5s', target:  20 },
                { duration: '30s', target:  20 },
            ],
            gracefulStop: '0s',
        },
    },
    thresholds: {
        http_req_duration: ["p(95)<6250", "avg<3000"],
    },
    summaryTrendStats: ['avg', 'p(95)']
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
    const res = http.get(`${BASE_URL}/news.php`);
    check(res, { "news OK": (r) => r.status === 200 });
}