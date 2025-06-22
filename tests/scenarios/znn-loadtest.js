import http from "k6/http";
import { check } from "k6";

export const options = {
    vus: 250,
    duration: "5m",
    thresholds: {
        http_req_duration: ["p(95)<2500"],
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
    const res = http.get(`${BASE_URL}/news.php`);
    check(res, { "news OK": (r) => r.status === 200 });
}