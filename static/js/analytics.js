/**
 * Systems³ Analytics Helper
 * Unified tracking wrapper for GA4 + Mixpanel.
 * Both platforms are optional — calls are no-ops when not loaded.
 */
(function () {
  'use strict';

  const S3 = window.S3Analytics = {};

  /* ── helpers ────────────────────────────────────────────────── */

  function ga4(eventName, params) {
    if (typeof gtag === 'function') {
      gtag('event', eventName, params || {});
    }
  }

  function mp(eventName, props) {
    if (window.mixpanel && typeof mixpanel.track === 'function') {
      mixpanel.track(eventName, props || {});
    }
  }

  /* ── public API ─────────────────────────────────────────────── */

  /**
   * Track a generic event on both platforms.
   * @param {string} name  Event name (e.g. "File Uploaded")
   * @param {object} [props]  Optional properties
   */
  S3.track = function (name, props) {
    ga4(name, props);
    mp(name, props);
  };

  /**
   * Identify a logged-in user (Mixpanel people profile + GA4 user_id).
   * @param {string} userId
   * @param {object} [traits]  e.g. { email, full_name, tier }
   */
  S3.identify = function (userId, traits) {
    if (typeof gtag === 'function') {
      gtag('set', { user_id: userId });
    }
    if (window.mixpanel && typeof mixpanel.identify === 'function') {
      mixpanel.identify(userId);
      if (traits) mixpanel.people.set(traits);
    }
  };

  /* ── pre-built events ───────────────────────────────────────── */

  /** User signed up */
  S3.signUp = function (method) {
    S3.track('sign_up', { method: method || 'email' });
  };

  /** User logged in */
  S3.login = function (method) {
    S3.track('login', { method: method || 'email' });
  };

  /** Project XML uploaded */
  S3.projectUploaded = function (projectCode, fileSizeMB) {
    S3.track('project_uploaded', {
      project_code: projectCode,
      file_size_mb: fileSizeMB,
    });
  };

  /** PowerPoint export generated */
  S3.exportGenerated = function (projectCode, format) {
    S3.track('export_generated', {
      project_code: projectCode,
      format: format || 'pptx',
    });
  };

  /** Dashboard view (specific tab) */
  S3.viewDashboard = function (tab, projectCode) {
    S3.track('dashboard_view', {
      tab: tab,
      project_code: projectCode || '',
    });
  };

  /** Feedback submitted */
  S3.feedbackSubmitted = function (type, priority) {
    S3.track('feedback_submitted', { type: type, priority: priority });
  };

  /** Feature used (generic) */
  S3.featureUsed = function (feature, details) {
    S3.track('feature_used', Object.assign({ feature: feature }, details || {}));
  };

  /* ── auto-track page views on SPA-style nav ────────────────── */

  // Track initial page view
  S3.track('page_view', { page: window.location.pathname });

})();
