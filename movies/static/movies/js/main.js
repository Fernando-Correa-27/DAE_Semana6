/* =============================================================================
   Catalogo de Peliculas - main.js
   Solo lo que Bootstrap JS NO hace. El bundle de Bootstrap ya gestiona
   dropdown, offcanvas, collapse, modal, toast y alert-dismissable: no se
   reimplementa nada de eso aqui.
   ========================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------------------------
     1. Doble envio
     Un <button type="submit"> (o input submit) se deshabilita en cuanto se
     envia su formulario para que un doble click no cree dos registros. El
     spinner lo pone el CSS a traves de la clase `is-loading`.
     ------------------------------------------------------------------------- */
  function guardSubmit(event) {
    var form = event.currentTarget;

    // Un boton marcado con data-bs-no-loading se deja intacto.
    var submitter = event.submitter;
    if (submitter && submitter.dataset.bsNoLoading !== undefined) {
      return;
    }

    var buttons = form.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type])');
    for (var i = 0; i < buttons.length; i += 1) {
      buttons[i].classList.add('is-loading');
      buttons[i].disabled = true;
    }

    // Red de seguridad: si la navegacion se cancela (validacion del navegador,
    // onsubmit que devuelve false) los botones volverian a quedar muertos.
    window.setTimeout(function () {
      for (var j = 0; j < buttons.length; j += 1) {
        buttons[j].disabled = false;
        buttons[j].classList.remove('is-loading');
      }
    }, 15000);
  }

  /* ---------------------------------------------------------------------------
     2. Cierre automatico de los mensajes flash
     A los 6s, solo si el elemento es realmente cerrable por Bootstrap. Si no
     hay bundle, el aviso se queda visible (mejor que desaparecer sin feedback).
     ------------------------------------------------------------------------- */
  var ALERT_TIMEOUT_MS = 6000;

  function scheduleAutoDismiss() {
    var alerts = document.querySelectorAll('.alert-dismissible[data-bs-dismiss="alert"]');
    if (!alerts.length) {
      return;
    }

    var hasBootstrapAlert = typeof window.bootstrap !== 'undefined' &&
      window.bootstrap.Alert &&
      typeof window.bootstrap.Alert.getOrCreateInstance === 'function';

    Array.prototype.forEach.call(alerts, function (alertEl) {
      if (alertEl.dataset.autoDismissed === 'true') {
        return;
      }
      alertEl.dataset.autoDismissed = 'true';

      window.setTimeout(function () {
        if (hasBootstrapAlert) {
          window.bootstrap.Alert.getOrCreateInstance(alertEl).close();
        } else {
          alertEl.classList.remove('show');
          alertEl.remove();
        }
      }, ALERT_TIMEOUT_MS);
    });
  }

  /* ---------------------------------------------------------------------------
     Arranque
     -------------------------------------------------------------------------- */
  function init() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }
    scheduleAutoDismiss();
  }

  // Delegacion: los formularios pueden aparecer tras una navegacion parcial.
  document.addEventListener('submit', guardSubmit);

  init();
})();
