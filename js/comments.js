/**
 * Комментарии к карточкам — поверх kvdb.io.
 *
 * UI:
 *   • На каждой карточке (в .card-footer) появляется кнопка-бейдж
 *     `.card-comments-btn` с эмодзи 💬. Бейдж подсвечивается классом
 *     `--has`, если у карточки уже есть хотя бы один комментарий.
 *     Точное количество не показываем — важен только факт наличия.
 *   • Клик по бейджу открывает оверлей `.comments-overlay`
 *     (fixed-position на body, не масштабируется зумом карточки).
 *   • Закрытие: клик по «×», Escape, или клик вне оверлея.
 *
 * Инициализация:
 *   На старте делаем один `bucket.list({ prefix: 'card_' })` (без values),
 *   получаем массив имён ключей `card_<ID>_comments` и помечаем
 *   соответствующие бейджи как has. Это самый дешёвый запрос — kvdb
 *   возвращает только имена ключей, тела не передаются.
 *
 * Стратегия хранения:
 *   ключ:    card_<ID>_comments
 *   значение: JSON-массив объектов { date, author, comment }
 *     date    — ISO-строка (new Date().toISOString())
 *     author  — имя автора, как ввёл пользователь
 *     comment — текст комментария
 *
 * Конфиг: window.KVDB_CONFIG = { bucket: '...', writeKey: '...' (опц.) }
 * Если bucket не задан — модуль не активируется (и в консоль идёт warn).
 *
 * Зависимости: kvdb.js (window.KVdb) и jQuery — загружаются раньше.
 */
$(function () {
  'use strict';

  var cfg = window.KVDB_CONFIG || {};
  if (!cfg.bucket) {
    console.warn('[comments] window.KVDB_CONFIG.bucket не задан — комментарии отключены. ' +
      'Создайте bucket на https://kvdb.io и пропишите его id в app.html.');
    return;
  }
  if (typeof window.KVdb === 'undefined') {
    console.error('[comments] kvdb.js не загружен');
    return;
  }

  var bucket = window.KVdb.bucket(cfg.bucket, cfg.writeKey || null);

  // ── Состояние модуля ─────────────────────────────────────────────
  // Имя автора больше не запрашивается и не хранится — все
  // новые комментарии анонимные. Старые комментарии с полем
  // author по-прежнему корректно отображаются.
  // Множество cardId, у которых на kvdb лежит ключ card_<ID>_comments
  // (используем объект-как-Set для совместимости и простоты).
  var commentedCards = {};        // { cardId: true }
  var $overlay       = null;      // открытый оверлей (или null)
  var currentCardId  = null;

  // ── Утилиты ──────────────────────────────────────────────────────
  function commentsKey(cardId) { return 'card_' + cardId + '_comments'; }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function fmtDate(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear() +
           ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function loadComments(cardId) {
    return bucket.getJSON(commentsKey(cardId)).then(function (data) {
      return Array.isArray(data) ? data : [];
    });
  }

  function saveComments(cardId, list) {
    return bucket.setJSON(commentsKey(cardId), list);
  }

  /**
   * Удалить один комментарий из массива по полю date.
   * Стратегия защиты от гонок: всегда re-load перед записью, чтобы
   * не затереть параллельные правки. Если после удаления массив пуст,
   * полностью убираем ключ из kvdb (иначе loadCommentedCards увидит
   * пустой массив и снова пометит карточку как «есть комментарии»).
   * Возвращает Promise с новым массивом.
   */
  function deleteComment(cardId, commentDate) {
    return loadComments(cardId).then(function (list) {
      var idx = -1;
      for (var i = 0; i < list.length; i++) {
        if (list[i] && list[i].date === commentDate) { idx = i; break; }
      }
      if (idx < 0) return list;        // уже удалён кем-то ещё
      list.splice(idx, 1);
      if (list.length === 0) {
        return bucket.del(commentsKey(cardId)).then(function () { return list; });
      }
      return saveComments(cardId, list).then(function () { return list; });
    });
  }

  // ── Бейдж на карточке ────────────────────────────────────────────
  function buildBadge(cardId) {
    var has = !!commentedCards[cardId];
    var $btn = $('<button>', {
      type:  'button',
      class: 'card-comments-btn' + (has ? ' card-comments-btn--has' : ''),
      'data-card-id': cardId,
      title: 'Комментарии'
    }).append(
      $('<span>', { class: 'card-comments-icon', html: '&#128172;' })
    );
    // Не пускаем клик к .card-item (иначе сработает зум)
    $btn.on('click', function (e) {
      e.stopPropagation();
      var $item = $(this).closest('.card-item');
      var title = $item.find('.card-title').first().text() || '';
      openComments(cardId, title);
    });
    $btn.on('mousedown', function (e) { e.stopPropagation(); });
    return $btn;
  }

  function attachBadges() {
    $('#grid .card-item').each(function () {
      var $item  = $(this);
      var cardId = parseInt($item.attr('data-card-id'), 10);
      if (!cardId) return;
      // Не дублируем
      if ($item.find('.card-comments-btn').length) return;
      var $footer = $item.find('.card-footer');
      if (!$footer.length) return;
      $footer.append(buildBadge(cardId));
    });
  }

  function markBadge(cardId, hasComments) {
    if (hasComments) commentedCards[cardId] = true;
    else             delete commentedCards[cardId];
    $('.card-comments-btn[data-card-id="' + cardId + '"]')
      .toggleClass('card-comments-btn--has', !!hasComments);
    // Проставляем атрибут на все .card-item с тем же id (включая
    // pseudo-копии в Корзине). Используется фильтром __comments__ в app.js.
    var $items = $('.card-item[data-card-id="' + cardId + '"]');
    if (hasComments) $items.attr('data-has-comments', '1');
    else             $items.removeAttr('data-has-comments');
    // Если активен фильтр «Комментарии», нужно пересчитать видимость:
    // карта могла только что получить (или потерять) метку.
    if (window.CardFilter && window.CardFilter.getMode() === '__comments__') {
      window.CardFilter.apply();
    }
  }

  // ── Массовая разметка бейджей на старте ─────────────────────────
  // Один list-запрос без values=true: kvdb возвращает только имена ключей
  // (например: ["card_5_comments","card_12_comments"]). Этого достаточно
  // чтобы понять, у каких карточек комментарии есть. Тела не качаем.
  function loadCommentedCards() {
    return bucket.list({ prefix: 'card_' }).then(function (entries) {
      (entries || []).forEach(function (entry) {
        // На всякий случай поддерживаем обе формы:
        //   "card_5_comments"           — без values
        //   ["card_5_comments", value]  — если кто-то позовёт с values=true
        var key = Array.isArray(entry) ? entry[0] : entry;
        var m = /^card_(\d+)_comments$/.exec(key || '');
        if (m) markBadge(parseInt(m[1], 10), true);
      });
    }).catch(function (err) {
      console.warn('[comments] не удалось загрузить список ключей:', err.message);
    });
  }

  // ── Кнопка фильтра «💬 Комментарии» ──────────────────────────────
  // Появляется в .filter-bar только после успешной загрузки списка
  // ключей с kvdb. До этого фильтра нет — нечем фильтровать.
  // Логика фильтрации живёт в app.js (case '__comments__'); видимость
  // карточек определяется по атрибуту data-has-comments, который мы
  // ставим в markBadge.
  function ensureCommentsFilterButton() {
    if (!window.CardFilter) return;                       // app.js не готов
    if (!$('.filter-btn--comments').length) {
      var $row = $('.filter-bar .filter-row').last();
      if (!$row.length) return;
      $('<button>', {
        type: 'button',
        class: 'filter-btn filter-btn--comments',
        // Кнопка приезжает после старта, когда язык уже выбран —
        // подпись берём из app.js, если он её отдаёт.
        text: (window.CardLang && window.CardLang.get() === 'en')
                ? '💬 Comments' : '💬 Комментарии',
        'data-type': '__comments__'
      })
        .on('click', function () {
          window.CardFilter.toggleMode('__comments__');
        })
        .appendTo($row);
    }
    // Если фильтр уже включён через location.hash, app.js успел вызвать
    // applyFilter ДО того как мы проставили data-has-comments —
    // в этот момент сетка была пуста. Пересчитываем сейчас.
    if (window.CardFilter.getMode() === '__comments__') {
      window.CardFilter.apply();
    }
  }

  // ── Оверлей с комментариями ──────────────────────────────────────
  function closeComments() {
    if (!$overlay) return;
    $overlay.remove();
    $overlay = null;
    currentCardId = null;
  }

  function openComments(cardId, cardTitle) {
    closeComments();
    currentCardId = cardId;

    var $list = $('<div>', { class: 'comments-list comments-list--loading', text: 'Загрузка…' });
    var $text = $('<textarea>', {
      class: 'comments-text',
      placeholder: 'Комментарий…',
      rows: 3, maxlength: 4000, required: true
    });
    var $err = $('<div>', { class: 'comments-error' }).hide();
    var $submit = $('<button>', {
      type: 'submit', class: 'comments-submit', text: 'Добавить'
    });
    var $form = $('<form>', { class: 'comments-form' })
      .append($text, $err, $submit);

    var $close = $('<button>', {
      type: 'button', class: 'comments-close',
      title: 'Закрыть (Esc)', html: '&times;'
    }).on('click', closeComments);

    var $header = $('<div>', { class: 'comments-overlay-header' }).append(
      $('<div>', { class: 'comments-overlay-titles' }).append(
        $('<span>', { class: 'comments-overlay-title', text: 'Комментарии' }),
        $('<span>', { class: 'comments-overlay-card', text: '#' + cardId + ' · ' + cardTitle })
      ),
      $close
    );

    $overlay = $('<div>', { class: 'comments-overlay' })
      .append($header, $list, $form);

    function render(comments) {
      $list.removeClass('comments-list--loading').empty();
      if (!comments.length) {
        $list.append($('<div>', { class: 'comments-empty', text: 'Пока нет комментариев.' }));
        return;
      }
      // Новые сверху
      comments.slice().reverse().forEach(function (c) {
        var $meta = $('<div>', { class: 'comment-meta' });
        // Author показываем только если он есть (старые комментарии могут
        // содержать поле author — новые сохраняются без него)
        if (c.author) {
          $meta.append($('<span>', { class: 'comment-author', text: c.author }));
        }
        $meta.append($('<span>', { class: 'comment-date', text: fmtDate(c.date) }));

        var $del = $('<button>', {
          type: 'button',
          class: 'comment-del',
          title: 'Удалить комментарий',
          html: '&times;'
        }).on('click', function (e) {
          e.stopPropagation();
          if (!window.confirm('Удалить этот комментарий?')) return;
          var $btn = $(this);
          $btn.prop('disabled', true);
          deleteComment(cardId, c.date).then(function (list) {
            render(list);
            markBadge(cardId, list.length > 0);
          }).catch(function (err) {
            var body = (err.body || '').trim();
            var msg  = body || err.message;
            window.alert('Не удалось удалить (' + (err.status || '?') + '): ' + msg);
            $btn.prop('disabled', false);
          });
        });

        $('<div>', { class: 'comment-item' }).append(
          $del,
          $meta,
          $('<div>', { class: 'comment-text', text: c.comment })
        ).appendTo($list);
      });
    }

    loadComments(cardId).then(function (list) {
      markBadge(cardId, list.length > 0);
      render(list);
    }).catch(function (err) {
      $list.removeClass('comments-list--loading').empty().append(
        $('<div>', { class: 'comments-empty comments-empty--error',
                     text: 'Не удалось загрузить: ' + err.message })
      );
    });

    $form.on('submit', function (e) {
      e.preventDefault();
      $err.hide();
      var text = $.trim($text.val());
      if (!text) return;

      $submit.prop('disabled', true).text('Сохраняю…');

      // Re-load перед записью, чтобы не затереть параллельные правки
      loadComments(cardId).then(function (list) {
        list.push({
          date:    new Date().toISOString(),
          comment: text
        });
        return saveComments(cardId, list).then(function () { return list; });
      }).then(function (list) {
        render(list);
        markBadge(cardId, list.length > 0);
        $text.val('');
      }).catch(function (err) {
        // Тело ответа kvdb обычно более информативно, чем "POST … → 403"
        // (например: «email address not verified. visit https://kvdb.io/login»).
        var body = (err.body || '').trim();
        var msg  = body ? body : err.message;
        $err.text('Ошибка сохранения (' + (err.status || '?') + '): ' + msg).show();
      }).then(function () {
        $submit.prop('disabled', false).text('Добавить');
      });
    });

    // Клики и mousedown внутри оверлея не должны провоцировать
    // глобальные хендлеры закрытия (свой и app.js).
    $overlay.on('click mousedown', function (e) { e.stopPropagation(); });
    // keydown тоже стопаем, чтобы Escape в textarea не рулил зумом app.js.
    // Но Escape внутри overlay должен закрывать оверлей — это делает
    // глобальный capture-listener ниже.
    $overlay.on('keydown', function (e) {
      if (e.key !== 'Escape') e.stopPropagation();
    });

    $('body').append($overlay);
    setTimeout(function () { $text.trigger('focus'); }, 0);
  }

  // ── Глобальные обработчики закрытия ─────────────────────────────
  // capture-фаза, чтобы успеть до document-level handler'ов app.js
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && $overlay) {
      closeComments();
      e.stopPropagation();
    }
  }, true);

  document.addEventListener('click', function (e) {
    if (!$overlay) return;
    if ($overlay[0].contains(e.target)) return;
    // Клик по бейджу другой карточки — не закрываем сразу,
    // обработчик бейджа сам перепереоткроет оверлей.
    var t = e.target;
    while (t) {
      if (t.classList && t.classList.contains('card-comments-btn')) return;
      t = t.parentNode;
    }
    closeComments();
  }, true);

  // ── Инициализация ───────────────────────────────────────────────
  // app.js рендерит карточки синхронно в своём $(ready); наш $(ready)
  // зарегистрирован позже, поэтому к моменту запуска этой функции
  // .card-item уже в DOM.
  setTimeout(function () {
    attachBadges();
    // Фильтр «Комментарии» доступен только после того как загрузится
    // список ключей с kvdb (даже если он пуст — это сигнал «модуль готов»).
    loadCommentedCards().then(ensureCommentsFilterButton);
  }, 0);

  // ── Экспорт для отладки ─────────────────────────────────────────
  window.CardComments = {
    bucket:   bucket,
    load:     loadComments,
    save:     saveComments,
    del:      deleteComment,
    keyFor:   commentsKey,
    open:     openComments,
    close:    closeComments,
    refresh:  loadCommentedCards,
    has:      function (cardId) { return !!commentedCards[cardId]; }
  };
});
