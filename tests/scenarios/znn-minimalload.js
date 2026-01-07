import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
    discardResponseBodies: true,
    scenarios: {
        contacts: {
            executor: "constant-arrival-rate",
            duration: "1h",
            rate: 40,
            timeUnit: "1s",
            preAllocatedVUs: 30,
            maxVUs: 150,
        },
    },
    thresholds: {
        http_req_duration: ["p(95)<1000"],
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const chance = 0.9;

export default function () {
    if (Math.random() <= chance) {
        const res = http.get(`${BASE_URL}/news.php`);
        check(res, { "news OK": (r) => r.status === 200 });
        sleep(0.5);
    } else {
	const res = http.get(`${BASE_URL}/error404.php`);
	check(res, { "404 OK": (r) => r.status === 404 });
	sleep(0.5);
    }
}
