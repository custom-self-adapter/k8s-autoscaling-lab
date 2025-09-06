import http from "k6/http";
import { check } from "k6";

export const options = {
    scenarios: {
        traffic: {
            executor: 'ramping-arrival-rate',
            timeUnit: '1s',
            startRate: 100,
            preAllocatedVUs: 200,
            maxVUs: 1600,
            stages: [
                { duration: '60s', target: 100},
                { duration: '15s', target: 400},
                { duration: '30s', target: 400},
                { duration:  '5s', target: 200},
                { duration: '45s', target: 200},
                { duration:  '5s', target: 600},
                { duration: '60s', target: 600},
                { duration:  '5s', target: 100},
                { duration: '60s', target: 100},
                { duration:  '5s', target: 400},
                { duration: '60s', target: 400},
                { duration:  '5s', target: 100},
                { duration:  '5s', target: 100},
            ],
            gracefulStop: '0s',
        },
    },
    thresholds: {
        http_req_duration: ["p(95)<1000", "avg<500"],
    },
    summaryTrendStats: ['avg', 'p(95)']
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
    const res = http.get(`${BASE_URL}/news.php`);
    check(res, { "news OK": (r) => r.status === 200 });
}