import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
    vus: 10,
    duration: "1h",
    thresholds: {
        http_req_duration: ["p(95)<1000"],
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const chance = 0.3;

export default function () {
    if (Math.random() <= chance){
        const res = http.get(`${BASE_URL}/news.php`);
        check(res, { "news OK": (r) => r.status === 200 });
        sleep(0.5);
    }
}