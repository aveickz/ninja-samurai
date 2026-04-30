/**
 * KVdb — минимальный браузерный клиент для https://kvdb.io
 *
 * Хранилище ключ-значение «как сервис». Работает поверх REST API:
 *   GET    /<bucket>/<key>          — получить значение
 *   POST   /<bucket>/<key>          — записать значение
 *   PATCH  /<bucket>/<key>  body=+1 — атомарный инкремент/декремент
 *   DELETE /<bucket>/<key>          — удалить ключ
 *   GET    /<bucket>/?prefix=…&format=json[&values=true] — список ключей
 *
 * Размеры: ключ ≤ 128 байт, значение ≤ 16 КБ.
 * TTL по умолчанию = 1 неделя (бесплатный план); для отключения TTL нужен Pro.
 *
 * Использование:
 *   var bucket = KVdb.bucket('BUCKET_ID', 'optional_access_token');
 *   await bucket.set('hello', 'world');
 *   var v = await bucket.get('hello');           // → 'world' или null
 *   await bucket.setJSON('user:1', { name: 'Иван' });
 *   var u = await bucket.getJSON('user:1');      // → { name: 'Иван' } или null
 *   await bucket.incr('hits', 1);                // → новое значение (строка)
 *   await bucket.del('hello');
 *   var keys = await bucket.list({ prefix: 'card_', values: true });
 *
 * Все методы возвращают Promise. 404 на get/getJSON/del трактуется как
 * «нет ключа» и резолвится в null без ошибки. Прочие не-2xx → reject(Error)
 * с полями `status` и `body`.
 */
(function (global) {
  'use strict';

  var BASE = 'https://kvdb.io';

  // ── Низкоуровневый HTTP ────────────────────────────────────────────
  function request(method, url, body, opts) {
    opts = opts || {};
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open(method, url, true);

      if (opts.token) {
        xhr.setRequestHeader('Authorization', 'Bearer ' + opts.token);
      }
      if (opts.contentType) {
        xhr.setRequestHeader('Content-Type', opts.contentType);
      }
      if (opts.accept) {
        xhr.setRequestHeader('Accept', opts.accept);
      }

      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(xhr.responseText);
        } else if (xhr.status === 404 && opts.notFoundOk) {
          resolve(null);
        } else {
          var err = new Error('KVdb ' + method + ' ' + url + ' → ' + xhr.status);
          err.status = xhr.status;
          err.body = xhr.responseText;
          reject(err);
        }
      };
      xhr.onerror = function () {
        reject(new Error('KVdb network error: ' + method + ' ' + url));
      };
      xhr.send(body == null ? null : body);
    });
  }

  function buildQuery(params) {
    if (!params) return '';
    var pairs = [];
    Object.keys(params).forEach(function (k) {
      var v = params[k];
      if (v == null) return;
      pairs.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
    return pairs.length ? '?' + pairs.join('&') : '';
  }

  // ── Bucket ─────────────────────────────────────────────────────────
  function Bucket(bucketId, token) {
    if (!bucketId) throw new Error('KVdb: bucket id обязателен');
    this.id = bucketId;
    this.token = token || null;
  }

  Bucket.prototype._url = function (key, query) {
    var path = BASE + '/' + encodeURIComponent(this.id);
    if (key != null) {
      path += '/' + encodeURIComponent(key);
    } else {
      // Листинг ключей требует завершающий слэш
      path += '/';
    }
    return path + buildQuery(query);
  };

  /**
   * Прочитать значение. Возвращает строку или null если ключа нет.
   */
  Bucket.prototype.get = function (key) {
    return request('GET', this._url(key), null, {
      token: this.token,
      notFoundOk: true
    });
  };

  /**
   * Прочитать значение и распарсить как JSON.
   * Возвращает разобранный объект или null если ключа нет / тело пустое.
   * Невалидный JSON → reject.
   */
  Bucket.prototype.getJSON = function (key) {
    return this.get(key).then(function (text) {
      if (text == null || text === '') return null;
      return JSON.parse(text);
    });
  };

  /**
   * Записать значение. value — строка/число.
   * opts.ttl — время жизни ключа в секундах (переопределяет default_ttl bucket'а).
   * opts.contentType — если не задан, подставляется text/plain.
   */
  Bucket.prototype.set = function (key, value, opts) {
    opts = opts || {};
    var query = {};
    if (opts.ttl != null) query.ttl = opts.ttl;
    return request('POST', this._url(key, query), String(value), {
      token: this.token,
      contentType: opts.contentType || 'text/plain'
    }).then(function () { return value; });
  };

  /**
   * Записать объект как JSON. TTL опционален.
   */
  Bucket.prototype.setJSON = function (key, obj, opts) {
    opts = opts || {};
    return this.set(key, JSON.stringify(obj), {
      ttl: opts.ttl,
      contentType: 'application/json'
    }).then(function () { return obj; });
  };

  /**
   * Удалить ключ. 404 → resolve(null) без ошибки.
   */
  Bucket.prototype.del = function (key) {
    return request('DELETE', this._url(key), null, {
      token: this.token,
      notFoundOk: true
    });
  };

  /**
   * Атомарно изменить числовой ключ. amount по умолчанию +1.
   * Возвращает новое значение в виде строки (как отвечает API).
   */
  Bucket.prototype.incr = function (key, amount) {
    if (amount == null) amount = 1;
    var op = amount >= 0 ? '+' + amount : String(amount);
    return request('PATCH', this._url(key), op, {
      token: this.token,
      contentType: 'text/plain'
    });
  };

  /**
   * Перечислить ключи в bucket'е.
   * opts.prefix  — фильтр по префиксу
   * opts.limit   — максимум элементов (по умолчанию 10000)
   * opts.skip    — пропустить N
   * opts.reverse — обратный порядок
   * opts.values  — если true, вернуть массив пар ['key', value]
   *
   * Возвращает массив строк (имена ключей) или массив [key, value] если values=true.
   * JSON-значения возвращаются как объекты (если key был сохранён с
   * Content-Type: application/json, например через setJSON).
   */
  Bucket.prototype.list = function (opts) {
    opts = opts || {};
    var query = { format: 'json' };
    if (opts.prefix != null) query.prefix = opts.prefix;
    if (opts.limit != null)  query.limit  = opts.limit;
    if (opts.skip != null)   query.skip   = opts.skip;
    if (opts.reverse)        query.reverse = 'true';
    if (opts.values)         query.values = 'true';

    return request('GET', this._url(null, query), null, {
      token: this.token,
      accept: 'application/json'
    }).then(function (text) {
      if (!text) return [];
      return JSON.parse(text);
    });
  };

  // ── Создание/удаление bucket'а ─────────────────────────────────────
  // Эти методы вспомогательные, обычно bucket создаётся один раз вручную
  // (через curl или сайт kvdb.io) и его id вписывается в приложение.

  /**
   * Создать новый bucket. Возвращает строку — id нового bucket'а.
   * opts.email      — обязателен для управления bucket'ом в будущем
   * opts.secret_key — полный доступ
   * opts.read_key   — ключ для чтения (если требуется приватность)
   * opts.write_key  — ключ для записи
   * opts.default_ttl — TTL ключей в секундах (0 = без истечения, нужен Pro)
   */
  function createBucket(opts) {
    opts = opts || {};
    if (!opts.email) {
      return Promise.reject(new Error('KVdb.createBucket: opts.email обязателен'));
    }
    var body = buildQuery(opts).replace(/^\?/, '');
    return request('POST', BASE + '/', body, {
      contentType: 'application/x-www-form-urlencoded'
    });
  }

  // ── Экспорт ────────────────────────────────────────────────────────
  global.KVdb = {
    bucket: function (bucketId, token) { return new Bucket(bucketId, token); },
    createBucket: createBucket,
    Bucket: Bucket,
    _BASE: BASE
  };

})(typeof window !== 'undefined' ? window : this);
