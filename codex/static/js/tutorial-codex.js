/* Nurro's tour of Codex.

   The callout itself is scifi-ui's holotip (tutorial-callout.js, the EyeWire II
   tutorial step). This file only decides when a tour starts and how it
   survives a change of page. A page that has a tour lists its steps in
   <ol class="holotip-steps" id="tour" hidden>; see the tour block in
   search.html and index.html.

   The story: the Tour link in the nav opens the search page on one cell type
   with ?tour=1, and the chapters hand off from there, search to cell to the
   cells that hear it. The tour runs by itself once per browser, about two
   seconds after a page with steps has loaded. While the story is on, any
   page the visitor wanders to keeps Nurro: a page with its own steps runs
   them, a page without shows one card with the way back. The once-per-browser
   flag is written only when the visitor ends the tour (Done, the close
   button, or Escape). */

(function () {
  "use strict";

  var KEY = "codexNurroTourSeen";
  var CHAPTER_KEY = "codexNurroTourChapter";
  var ACTIVE_KEY = "codexNurroTourActive";
  var TTL = 30 * 60 * 1000;   /* a story left half told is forgotten after half an hour */
  var DELAY = 2000;

  /* localStorage, not sessionStorage, because the out links open new tabs */
  function read(key) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return null;
      var v = JSON.parse(raw);
      if (!v || Date.now() - v.t > TTL) { localStorage.removeItem(key); return null; }
      return v;
    } catch (e) { return null; }
  }
  function write(key, value) {
    try {
      if (value) { value.t = Date.now(); localStorage.setItem(key, JSON.stringify(value)); }
      else localStorage.removeItem(key);
    } catch (e) { /* storage may be off */ }
  }

  /* A hand off step names the chapter the next page should open with; the
     page picks the step list whose data-holotip-chapter matches, or its
     default list. */
  function chapter() { var c = read(CHAPTER_KEY); return c ? c.name : null; }
  function setChapter(name) { write(CHAPTER_KEY, name ? { name: name } : null); }

  /* the story is on: where it is, and which step, so a page can pick it up */
  function active() { return read(ACTIVE_KEY); }
  function setActive(url, step) { write(ACTIVE_KEY, url ? { url: url, step: step || 0 } : null); }

  function seen() {
    try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; }
  }
  function remember() {
    try { localStorage.setItem(KEY, "1"); } catch (e) { /* storage may be off */ }
  }

  /* this page's address without the tour switch */
  function here() {
    var u = new URL(window.location.href);
    u.searchParams.delete("tour");
    return u.href;
  }

  /* A target that is in the DOM but not on screen (a nav link inside the
     collapsed phone menu) would pin the callout to the top left corner. A
     centred card with no beak is what holotip already does for a missing
     target, so an unseen target is treated as missing. */
  function shown(selector) {
    var t = selector && document.querySelector(selector);
    return !!(t && t.getClientRects().length);
  }

  var current = null;

  function listFor(name) {
    var list = name && document.querySelector('.holotip-steps[data-holotip-chapter="' + name + '"]');
    return list || document.getElementById("tour");
  }

  /* the story's bookkeeping on any tour: each step is noted, so a page change
     mid chapter comes back to the same step; the end clears everything */
  function wrap(tour, track) {
    var stopped = tour.stop.bind(tour);
    var went = tour.go.bind(tour);
    tour.rawStop = stopped;
    tour.go = function (i) {
      if (track) setActive(here(), i);
      return went(i);
    };
    tour.stop = function () {
      remember();
      setChapter(null);
      setActive(null);
      if (current === tour) current = null;
      return stopped();
    };
    /* a hand off keeps the story alive: the next page opens on its chapter */
    tour.onHandoff = function (step) { if (step.goto) setChapter(step.goto); };
    return tour;
  }

  function build(name) {
    if (!window.holotip) return null;
    var list = listFor(name);
    if (!list) return null;
    var tour = window.holotip.fromList(list);
    if (!tour) return null;
    tour.steps.forEach(function (s) { if (!shown(s.target)) s.target = null; });
    return wrap(tour, true);
  }

  /* a page with no steps of its own, while the story is on: one card that
     says so, with the way back */
  function buildResume(url, guide) {
    if (!window.holotip) return null;
    var tour = window.holotip([{
      target: null, side: "bottom", title: "Still on the tour", nextLabel: "End the tour", guide: guide || null,
      html: '<p>This page has no steps of its own yet; everything here you find by clicking. ' +
            '<a href="' + url.replace(/"/g, "&quot;") + '">Back to the story</a> picks up where we were.</p>'
    }]);
    return wrap(tour, false);
  }

  function start(name, from) {
    if (current) { var old = current; current = null; old.rawStop(); }
    current = build(name);
    if (current) current.start(from || 0);
    return current;
  }

  function init() {
    var list = document.getElementById("tour");
    var link = document.getElementById("nav_tour");
    var home = link && link.getAttribute("data-tour-home");
    var forced = /[?&]tour=1(?:&|$)/.test(window.location.search);

    /* the home page's own tour gave way to the story: ?tour=1 there goes to the story's first page */
    if (forced && home && link.getAttribute("data-tour-index") === "1") { window.location.replace(home); return; }

    var name = chapter();
    var act = active();
    if (list) {
      /* the same page, mid chapter: back to the step we were on */
      var from = act && act.url === here() && !name ? act.step : 0;
      if (forced || name || act || !seen()) {
        window.setTimeout(function () { start(forced ? null : name, forced ? 0 : from); }, forced ? 300 : DELAY);
      }
    } else if (act) {
      window.setTimeout(function () {
        current = buildResume(act.url, link && link.getAttribute("data-tour-guide"));
        if (current) current.start();
      }, 300);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* for checks from outside; nothing on the page reads this */
  window.codexTour = { start: start, key: KEY, chapterKey: CHAPTER_KEY, activeKey: ACTIVE_KEY,
    get chapter() { return chapter(); }, get active() { return active(); }, get current() { return current; } };
})();
