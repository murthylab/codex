/* ---- tutorial callout (holotip) -----------------------------------------
   Builds and drives the callout defined in tutorial-callout.css.

   Two ways in. Declarative, which keeps the copy in the HTML:

     <ol class="holotip-steps" id="tour" hidden>
       <li data-holotip-target="#rail" data-holotip-side="bottom"
           data-holotip-title="The rail">
         <p>Any markup you like.</p>
       </li>
     </ol>
     <button data-holotip-start="#tour">Take the tour</button>

   or from script:

     const tour = holotip([{ target: "#rail", side: "bottom",
                             title: "The rail", html: "<p>Copy.</p>" }]);
     tour.start();          // also .next() .prev() .go(i) .stop()

   The panel is position fixed and nothing here listens for wheel or touch,
   so the page keeps its own scrolling. Escape dismisses. Left and right
   arrows step. The whole thing is removed from the DOM on stop and focus
   goes back to whatever opened it.

   Codex copy of scifi-ui's tutorial-callout.js. One addition: a step can
   name its own guide sprite with data-holotip-guide (or a guide field),
   which is applied to the card as the --holotip-guide custom property and
   read by tutorial-nurro.css. */

(function () {
  "use strict";

  var GAP = 14;   /* clearance between target and panel, matches the beak */
  var EDGE = 8;   /* smallest gap allowed between panel and viewport edge  */
  var CORNER = 20; /* keeps the beak clear of the rounded corners          */

  var reduce = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : { matches: false };

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function el(tag, cls) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }

  var uid = 0;

  function Tour(steps, options) {
    this.steps = steps || [];
    this.options = options || {};
    this.index = -1;
    this.node = null;
    this.target = null;
    this.opener = null;
    this.id = "holotip-" + (++uid);
    this._onScroll = this._reposition.bind(this);
    this._onKey = this._key.bind(this);
    this._onDocKey = this._docKey.bind(this);
  }

  Tour.prototype.start = function (from) {
    if (!this.steps.length) return this;
    this.opener = document.activeElement;
    this.go(typeof from === "number" ? from : 0);
    window.addEventListener("scroll", this._onScroll, true);
    window.addEventListener("resize", this._onScroll);
    document.addEventListener("keydown", this._onDocKey);
    return this;
  };

  Tour.prototype.stop = function () {
    window.removeEventListener("scroll", this._onScroll, true);
    window.removeEventListener("resize", this._onScroll);
    document.removeEventListener("keydown", this._onDocKey);
    this._clearTarget();
    if (this.node) { this.node.remove(); this.node = null; }
    this.index = -1;
    var o = this.opener;
    this.opener = null;
    if (o && o.focus) o.focus();
    return this;
  };

  Tour.prototype.next = function () {
    if (this.index >= this.steps.length - 1) return this.stop();
    return this.go(this.index + 1);
  };

  Tour.prototype.prev = function () {
    if (this.index <= 0) return this;
    return this.go(this.index - 1);
  };

  Tour.prototype._clearTarget = function () {
    if (this._cycle) { clearInterval(this._cycle); this._cycle = null; }
    if (this._handoffOff) { this._handoffOff(); this._handoffOff = null; }
    if (this._popGroup) { this._popGroup.forEach(function (g) { g.classList.remove("holotip-pop"); }); this._popGroup = null; }
    if (this.target) {
      this.target.classList.remove("holotip-target");
      this.target = null;
    }
  };

  /* point the open card at another element, without rebuilding it */
  Tour.prototype._retarget = function (target, phase) {
    if (this.target) this.target.classList.remove("holotip-target");
    this.target = target || null;
    if (target) {
      target.classList.add("holotip-target");
      if (!this._inView(target)) this._reveal(target);
    }
    if (this.node) {
      var marks = this.node.querySelectorAll("[data-holotip-phase]");
      Array.prototype.forEach.call(marks, function (m) {
        m.classList.toggle("is-on", m.getAttribute("data-holotip-phase") === String(phase));
      });
      this.node.classList.add("is-moving");
    }
    this._reposition();
  };

  Tour.prototype.go = function (i) {
    var step = this.steps[i];
    if (!step) return this;
    this.index = i;
    this._clearTarget();

    /* rebuilt per step rather than patched, so the entrance and the letter
       reveal replay on every step instead of only on the first one */
    if (this.node) this.node.remove();
    var node = this.node = this._build(step, i);
    document.body.appendChild(node);

    var target = step.target ? document.querySelector(step.target) : null;
    if (target) {
      this.target = target;
      target.classList.add("holotip-target");
      if (!this._inView(target)) this._reveal(target);
    }

    this._reposition();
    node.focus();

    /* a hand off: the visitor's click on the target is the Next button. With
       no target on screen there is nothing to click, so Next stays. */
    if (step.await === "click" && target) {
      var nextBtn = node.querySelector(".holotip-next");
      if (nextBtn) nextBtn.style.display = "none";
      {
        var self2 = this;
        var onClick = function () {
          target.removeEventListener("click", onClick, true);
          if (typeof self2.onHandoff === "function") self2.onHandoff(step);
        };
        target.addEventListener("click", onClick, true);
        this._handoffOff = function () { target.removeEventListener("click", onClick, true); };
      }
    }

    /* a step that names a group pops each member in turn; motion off leaves
       them still, since a pop is decoration and the card already points at the bar */
    if (step.pop && !reduce.matches) {
      var group = Array.prototype.slice.call(document.querySelectorAll(step.pop));
      if (group.length) {
        var k = -1, tour = this;
        var pop = function () {
          if (k >= 0) group[k].classList.remove("holotip-pop");
          k = (k + 1) % group.length;
          group[k].classList.remove("holotip-pop"); void group[k].offsetWidth;
          group[k].classList.add("holotip-pop");
        };
        pop();
        this._cycle = setInterval(pop, step.cycle || 800);
        this._popGroup = group;
      }
    }

    /* a step with several targets walks between them; motion off shows the
       first and lights every phase word, so nothing is withheld */
    if (step.targets && step.targets.length > 1) {
      var self = this, phase = 0;
      var els = step.targets.map(function (sel) { return document.querySelector(sel); });
      if (reduce.matches) {
        Array.prototype.forEach.call(node.querySelectorAll("[data-holotip-phase]"), function (m) { m.classList.add("is-on"); });
      } else if (els.every(Boolean)) {
        this._retarget(els[0], 0);
        this._cycle = setInterval(function () {
          phase = (phase + 1) % els.length;
          self._retarget(els[phase], phase);
        }, step.cycle || 3000);
      }
    }
    return this;
  };

  Tour.prototype._inView = function (t) {
    var r = t.getBoundingClientRect();
    return r.top >= 0 && r.bottom <= document.documentElement.clientHeight;
  };

  /* Bring the target on screen, then make sure it actually happened.

     A smooth scroll is animated by the compositor, so in any context without
     a frame loop, a background tab or an embedded pane that reports the
     document hidden, the request is accepted and nothing moves. Measured in
     one of those: scrollIntoView with behavior auto arrived at 1312px, the
     same call with behavior smooth left the page at 0 and stayed there.

     A tour whose target is off screen is broken, so ask for the smooth scroll,
     then check, and jump if the page did not move. */
  Tour.prototype._reveal = function (target) {
    var self = this;
    var where = { block: "center", inline: "nearest" };

    if (reduce.matches) {
      target.scrollIntoView(where);
      return;
    }

    var before = window.pageYOffset;
    where.behavior = "smooth";
    target.scrollIntoView(where);

    window.setTimeout(function () {
      if (window.pageYOffset !== before || self.target !== target) return;
      delete where.behavior;
      target.scrollIntoView(where);
      self._reposition();
    }, 120);
  };

  Tour.prototype._build = function (step, i) {
    var self = this;
    var total = this.steps.length;
    /* a chapter of a longer story counts from where the story is */
    var off = this.options.offset || 0, tot = this.options.total || total;

    var node = el("div", "holotip");
    node.tabIndex = -1;
    node.setAttribute("role", "dialog");
    node.setAttribute("aria-modal", "false");
    node.style.setProperty("--holotip-progress", (i + 1 + off) / tot);
    if (step.guide) node.style.setProperty("--holotip-guide", 'url("' + step.guide + '")');

    var beak = el("i", "holotip-beak");
    beak.setAttribute("aria-hidden", "true");
    node.appendChild(beak);

    ["tl", "tr", "bl", "br"].forEach(function (c) {
      var s = el("span", "holotip-corner holotip-corner--" + c);
      s.setAttribute("aria-hidden", "true");
      node.appendChild(s);
    });

    var close = el("button", "holotip-close");
    close.type = "button";
    close.setAttribute("aria-label", "End the tour");
    close.textContent = "×";
    close.addEventListener("click", function () { self.stop(); });
    node.appendChild(close);

    if (step.title) {
      var h = el("h2", "holotip-title");
      h.id = this.id + "-title-" + i;
      /* the accessible name is the whole title, not the letter spans */
      h.setAttribute("aria-label", step.title);
      /* letters are grouped by word, so a long title wraps between words
         and never in the middle of one */
      var n = 0;
      String(step.title).split(" ").forEach(function (word, w) {
        if (w > 0) {
          var sp = el("span", "holotip-letter");
          sp.setAttribute("aria-hidden", "true");
          sp.textContent = " ";
          h.appendChild(sp);
          n++;
        }
        var wrap = el("span", "holotip-word");
        wrap.setAttribute("aria-hidden", "true");
        word.split("").forEach(function (ch) {
          var s = el("span", "holotip-letter");
          /* capped stagger. Uncapped, a long title is still assembling after
             the reader has moved on to the body copy */
          s.style.animationDelay = Math.min(n * 0.022, 0.24) + "s";
          s.textContent = ch;
          wrap.appendChild(s);
          n++;
        });
        h.appendChild(wrap);
      });
      node.appendChild(h);
      node.setAttribute("aria-labelledby", h.id);
    } else {
      node.setAttribute("aria-label", "Tour step " + (i + 1 + off) + " of " + tot);
    }

    var body = el("div", "holotip-body");
    body.id = this.id + "-body-" + i;
    if (step.html) body.innerHTML = step.html;
    else if (step.text) body.textContent = step.text;
    node.appendChild(body);
    node.setAttribute("aria-describedby", body.id);

    var actions = el("div", "holotip-actions");

    if (i > 0) {
      var back = el("button", "holotip-back");
      back.type = "button";
      back.textContent = step.backLabel || "back";
      back.addEventListener("click", function () { self.prev(); });
      actions.appendChild(back);
    }

    var next = el("button", "holotip-next");
    next.type = "button";
    next.textContent = step.nextLabel || (i === total - 1 ? "done" : "next");
    next.addEventListener("click", function () { self.next(); });
    actions.appendChild(next);

    var count = el("span", "holotip-count");
    count.setAttribute("aria-hidden", "true");
    count.textContent = (i + 1 + off) + "/" + tot;
    actions.appendChild(count);

    node.appendChild(actions);

    var rail = el("div", "holotip-rail");
    rail.setAttribute("aria-hidden", "true");
    rail.appendChild(el("i"));
    node.appendChild(rail);

    node.addEventListener("keydown", this._onKey);
    return node;
  };

  /* ---- placement -------------------------------------------------------
     Put the panel on the requested side, flip to the opposite side if it
     does not fit there, clamp the result into the viewport, then slide the
     beak along the panel edge so it still points at the target. */
  Tour.prototype._reposition = function () {
    var node = this.node;
    if (!node) return;
    var step = this.steps[this.index] || {};
    var t = this.target ? this.target.getBoundingClientRect() : null;

    var vw = document.documentElement.clientWidth;
    var vh = document.documentElement.clientHeight;
    var w = node.offsetWidth;
    var h = node.offsetHeight;

    if (!t) {
      node.setAttribute("data-side", "center");
      node.style.left = Math.round((vw - w) / 2) + "px";
      node.style.top = Math.round((vh - h) / 2) + "px";
      return;
    }

    var side = step.side || "bottom";
    var fits = {
      bottom: t.bottom + GAP + h <= vh - EDGE,
      top: t.top - GAP - h >= EDGE,
      right: t.right + GAP + w <= vw - EDGE,
      left: t.left - GAP - w >= EDGE
    };
    var opposite = { bottom: "top", top: "bottom", right: "left", left: "right" };
    if (!fits[side] && fits[opposite[side]]) side = opposite[side];

    var left, top;
    if (side === "bottom" || side === "top") {
      left = t.left + t.width / 2 - w / 2;
      top = side === "bottom" ? t.bottom + GAP : t.top - GAP - h;
    } else {
      left = side === "right" ? t.right + GAP : t.left - GAP - w;
      top = t.top + t.height / 2 - h / 2;
    }

    left = clamp(left, EDGE, Math.max(EDGE, vw - w - EDGE));
    top = clamp(top, EDGE, Math.max(EDGE, vh - h - EDGE));

    node.setAttribute("data-side", side);
    node.style.left = Math.round(left) + "px";
    node.style.top = Math.round(top) + "px";

    /* the beak keeps pointing at the target centre even after the clamp
       moved the panel, and never rides up onto a rounded corner */
    if (side === "bottom" || side === "top") {
      var bx = clamp(t.left + t.width / 2 - left, CORNER, Math.max(CORNER, w - CORNER));
      node.style.setProperty("--holotip-beak", Math.round(bx) + "px");
    } else {
      var by = clamp(t.top + t.height / 2 - top, CORNER, Math.max(CORNER, h - CORNER));
      node.style.setProperty("--holotip-beak", Math.round(by) + "px");
    }
  };

  Tour.prototype._key = function (e) {
    if (e.key === "ArrowRight") { e.preventDefault(); this.next(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); this.prev(); }
  };

  /* Escape from anywhere, because focus can leave the panel with one click.
     Nothing else is captured at document level: swallowing Enter globally
     breaks every form on the host page. */
  Tour.prototype._docKey = function (e) {
    if (e.key === "Escape") { e.preventDefault(); this.stop(); }
  };

  function holotip(steps, options) { return new Tour(steps, options); }

  /* read a step list out of the DOM */
  holotip.fromList = function (listOrSelector) {
    var list = typeof listOrSelector === "string"
      ? document.querySelector(listOrSelector) : listOrSelector;
    if (!list) return null;
    var steps = [];
    Array.prototype.forEach.call(list.children, function (li) {
      steps.push({
        target: li.getAttribute("data-holotip-target") || null,
        side: li.getAttribute("data-holotip-side") || "bottom",
        title: li.getAttribute("data-holotip-title") || "",
        nextLabel: li.getAttribute("data-holotip-next") || null,
        guide: li.getAttribute("data-holotip-guide") || null,
        /* "sel1|sel2": the card moves between them every `cycle` ms, and any
           [data-holotip-phase=N] inside the card lights while target N is up */
        targets: (li.getAttribute("data-holotip-targets") || "").split("|").map(function (x) { return x.trim(); }).filter(Boolean),
        cycle: parseInt(li.getAttribute("data-holotip-cycle"), 10) || 0,
        /* a selector matching several elements: the card stays put and each
           one pops in turn, every `cycle` ms */
        pop: li.getAttribute("data-holotip-pop") || null,
        /* await="click": Next is hidden and the step ends when the visitor clicks
           the target, which is how a story hands off to the page that opens */
        await: li.getAttribute("data-holotip-await") || null,
        goto: li.getAttribute("data-holotip-goto") || null,
        html: li.innerHTML
      });
    });
    /* data-holotip-offset and data-holotip-total on the list: this chapter's place in a longer story */
    return holotip(steps, { offset: parseInt(list.getAttribute("data-holotip-offset"), 10) || 0, total: parseInt(list.getAttribute("data-holotip-total"), 10) || 0 });
  };

  /* wire up any button that names a step list */
  holotip.init = function (root) {
    var scope = root || document;
    var buttons = scope.querySelectorAll("[data-holotip-start]");
    Array.prototype.forEach.call(buttons, function (btn) {
      if (btn.holotipBound) return;
      btn.holotipBound = true;
      btn.addEventListener("click", function () {
        var tour = holotip.fromList(btn.getAttribute("data-holotip-start"));
        if (tour) tour.start();
      });
    });
  };

  window.holotip = holotip;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { holotip.init(); });
  } else {
    holotip.init();
  }
})();
