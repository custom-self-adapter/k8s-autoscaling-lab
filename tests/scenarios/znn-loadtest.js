import http from "k6/http";
import { check } from "k6";

export const options = {
    scenarios: {
        traffic: {
            executor: 'constant-vus',
            vus: 500,
            duration: '10m',
        },
    },
    thresholds: {
        http_req_duration: ["p(95)<500", "avg<300"],
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
    const res = http.get(`${BASE_URL}/news.php`);
    check(res, { "news OK": (r) => r.status === 200 });
}