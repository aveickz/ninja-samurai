/* ============================================================
   typograph.js — лёгкая типографическая обработка страницы
   ------------------------------------------------------------
   Проходит по всем текстовым узлам документа и заменяет обычный
   пробел после одно- и двухбуквенных предлогов, союзов и частиц
   на неразрывный (U+00A0). Так короткие слова не «висят»
   в конце строки и не отрываются от следующего слова.

   Запускается автоматически после загрузки DOM. Игнорирует
   содержимое <script>, <style>, <code>, <pre>, <textarea>, <kbd>.
   ============================================================ */

(function () {
  'use strict';

  // Одно- и двухбуквенные служебные слова (русский язык).
  // Каждый вариант перечислен в обоих регистрах через [Аа]-нотацию.
  var SHORT_WORDS = [
    // 1 буква — предлоги/союзы/частицы + местоимение «я»
    '[АаВвИиКкОоСсУуЯя]',

    // 2 буквы — предлоги/союзы/частицы
    '[Бб]ы', '[Вв]о', '[Дд]о', '[Жж]е', '[Зз]а', '[Ии]з', '[Кк]о',
    '[Лл]и', '[Нн]а', '[Нн]е', '[Нн]и', '[Нн]о', '[Оо]б', '[Оо]т',
    '[Пп]о', '[Сс]о', '[Тт]о', '[Дд]а',

    // 2 буквы — местоимения
    '[Вв]ы', '[Мм]ы', '[Тт]ы', '[Оо]н',
    '[Ее][её]',                          // ее, её, Ее, Её
    '[Ее]й', '[Ее]ю', '[Ии]м', '[Ии]х'
  ];

  // Регулярка:
  //   (?<![\p{L}\p{N}])  — слева от слова не должна стоять буква/цифра
  //                       (то есть слово стоит само по себе);
  //   ( ... )            — само служебное слово;
  //   ' '                — обычный пробел после него (именно один,
  //                       чтобы не трогать табы и переносы строк);
  //   (?=[\p{L}\p{N}])   — справа должно быть слово.
  // Флаг u включает поддержку Unicode property escapes.
  var PATTERN = new RegExp(
    '(?<![\\p{L}\\p{N}])(' + SHORT_WORDS.join('|') + ') (?=[\\p{L}\\p{N}])',
    'gu'
  );

  // Замена: само слово + неразрывный пробел (U+00A0).
  // Явная escape-последовательность — чтобы исходник не зависел
  // от того, как любой редактор/копипаст обрабатывает невидимый символ.
  var NBSP_REPLACEMENT = '$1\u00A0';

  // Теги, внутрь которых лезть не надо.
  var SKIP_TAGS = {
    SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, TEXTAREA: 1, KBD: 1
  };

  function shouldSkip(textNode) {
    var p = textNode.parentNode;
    while (p && p.nodeType === 1) {
      if (SKIP_TAGS[p.tagName]) return true;
      // contenteditable обходим стороной — пользователь может
      // редактировать и непредсказуемо потерять курсор.
      if (p.isContentEditable) return true;
      p = p.parentNode;
    }
    return false;
  }

  function process(root) {
    var walker = document.createTreeWalker(
      root,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: function (node) {
          if (shouldSkip(node)) return NodeFilter.FILTER_REJECT;
          if (!node.nodeValue || !node.nodeValue.trim()) {
            return NodeFilter.FILTER_SKIP;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    // Сначала собираем все узлы, потом меняем — иначе обход
    // может «потеряться» при модификациях.
    var nodes = [];
    var n;
    while ((n = walker.nextNode())) nodes.push(n);

    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var before = node.nodeValue;
      var after = before.replace(PATTERN, NBSP_REPLACEMENT);
      if (after !== before) node.nodeValue = after;
    }
  }

  /* Копируем data-mark с h2.chapter-title на родительский
     section.chapter — чтобы CSS section.chapter::before мог
     прочитать атрибут через attr(data-mark). Так удалось
     обойтись без 14 правок HTML. */
  function syncChapterMarks() {
    var titles = document.querySelectorAll(
      'section.chapter > h2.chapter-title[data-mark]'
    );
    for (var i = 0; i < titles.length; i++) {
      var h2 = titles[i];
      var section = h2.parentNode;
      if (section && !section.hasAttribute('data-mark')) {
        section.setAttribute('data-mark', h2.getAttribute('data-mark'));
      }
    }
  }

  function run() {
    syncChapterMarks();
    process(document.body);
  }

  // Базовый запуск — после загрузки DOM.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }

  // Повторный запуск после того, как paged.js (если он подключён)
  // перестроит документ на «листы». Хук должен быть установлен
  // ДО загрузки paged.js — поэтому этот скрипт идёт раньше в HTML.
  // Повторная обработка идемпотентна: после первого прохода
  // между служебным словом и следующим уже стоит U+00A0,
  // регулярка ищет обычный пробел и такой случай не трогает.
  window.PagedConfig = window.PagedConfig || {};
  var prevAfter = window.PagedConfig.after;
  window.PagedConfig.after = function (flow) {
    if (typeof prevAfter === 'function') prevAfter(flow);
    run();
  };
})();
