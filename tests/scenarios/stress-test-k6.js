import http from "k6/http";
import { randomItem } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";
import { check } from "k6";

export const options = {
  vus: 500,
  duration: "5m",
  thresholds: {
    http_req_duration: ["p(95)<1000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

const products = [
  "0PUK6V6EV0",
  "1YMWWN1N4O",
  "2ZYFJ3GM2N",
  "66VCHSJNUP",
  "6E92ZMYYFZ",
  "9SIQT8TOJO",
  "L9ECAV7KIM",
  "LS4PSXUNUM",
  "OLJCESPC7Z",
];

const currencies = ["EUR", "USD", "JPY", "CAD"];

function index() {
  const res = http.get(`${BASE_URL}/`);
  check(res, { "index OK": (r) => r.status === 200 });
}

function setCurrency() {
  const res = http.post(`${BASE_URL}/setCurrency`, {
    currency_code: randomItem(currencies),
  });
  check(res, { "currency OK": (r) => r.status === 200 });
}

function browseProduct() {
  const res = http.get(`${BASE_URL}/product/${randomItem(products)}`);
  check(res, { "product OK": (r) => r.status === 200 });
}

function viewCart() {
  const res = http.get(`${BASE_URL}/cart`);
  check(res, { "view cart OK": (r) => r.status === 200 });
}

function addToCart() {
  const product = randomItem(products);
  http.get(`${BASE_URL}/product/${product}`);
  const res = http.post(`${BASE_URL}/cart`, {
    product_id: product,
    quantity: randomItem([1, 2, 3, 4, 5, 10]),
  });
  check(res, { "add to cart OK": (r) => r.status === 200 });
}

function checkout() {
  addToCart();
  const res = http.post(`${BASE_URL}/cart/checkout`, {
    email: "someone@example.com",
    street_address: "1600 Amphitheatre Parkway",
    zip_code: "94043",
    city: "Mountain View",
    state: "CA",
    country: "United States",
    credit_card_number: "4432801561520454",
    credit_card_expiration_month: "1",
    credit_card_expiration_year: "2039",
    credit_card_cvv: "672",
  });
  check(res, { "checkout OK": (r) => r.status >= 200 && r.status < 300 });
}

const actions = [
  { weight: 1, func: index },
  { weight: 2, func: setCurrency },
  { weight: 10, func: browseProduct },
  { weight: 3, func: viewCart },
  { weight: 2, func: addToCart },
  { weight: 1, func: checkout },
];

export default function () {
  const totalWeight = actions.reduce((sum, a) => sum + a.weight, 0);
  let r = Math.random() * totalWeight;
  for (const action of actions) {
    if (r < action.weight) {
      action.func();
      break;
    }
    r -= action.weight;
  }
}
