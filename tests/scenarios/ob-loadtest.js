import http from 'k6/http';
import { check, fail, sleep } from 'k6';
import { parseHTML } from 'k6/html';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.6.0/index.js';
import formUrlencoded from 'https://jslib.k6.io/form-urlencoded/3.0.0/index.js';

export const options = {
  scenarios: {
    ob_stress: {
      executor: 'ramping-arrival-rate',
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 1000,
      stages: [
        { target: 50,  duration: '2m' },
        { target: 250, duration: '3m' },
        { target: 600, duration: '5m' },
        { target: 0,   duration: '1m' }
      ]
    }
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500']
  }
};

const BASE = __ENV.BASE_URL || 'http://boutique.k8s.lab';

export default function () {
  // 1. catálogo
  let res = http.get(`${BASE}`);
  check(res, { 'home OK': r => r.status === 200 });

  // obtém um produto aleatório dentro de hot-product-card
  const doc = parseHTML(res.body);
  const links = doc.find('.hot-product-card a');

  if (!links.size()) {
    fail('no products found');
  }

  const hrefs = links.map((_, el) => el.attr('href'));
  const href = randomItem(hrefs);
  const prodId = href.split('/').pop();

  // 2. página do produto
  res = http.get(`${BASE}/product/${prodId}`);
  check(res, { 'product OK': r => r.status === 200 });
  sleep(1);

  // 3. adicionar ao carrinho
  const cartBody = formUrlencoded({ 'product_id': prodId, 'quantity': 1 });
  res = http.post(`${BASE}/cart`, cartBody, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
  check(res, {'cart OK': r => r.status === 200 });
  sleep(1);

  // 4. alternar moeda
  const currencies = ['USD', 'BRL', 'EUR', 'CAD', 'JPY'];
  http.post(`${BASE}/setCurrency`,
            formUrlencoded({ currency_code: randomItem(currencies) }),
            { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });

  // 5. checkout eventual
  if (Math.random() < 0.3) {
    const payload = formUrlencoded({
      'email': 'someone@example.com',
      'street_address': 'Rua A',
      'zip_code': '60000',
      'city': 'Fortaleza',
      'state': 'CE',
      'country': 'Brazil',
      'credit_card_number': '4111111111111111',
      'credit_card_cvv': 123,
      'credit_card_expiration_month': 1,
      'credit_card_expiration_year': 2030
    });
    res = http.post(`${BASE}/cart/checkout`, payload, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
    check(res, { 'checkout OK': r => r.status >= 200 && r.status < 300 });
  }

  sleep(2);
}
