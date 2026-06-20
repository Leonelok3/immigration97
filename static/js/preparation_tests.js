(function () {
  "use strict";

  function closest(el, selector) {
    while (el && el !== document) {
      if (el.matches(selector)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function setFeedback(form, msg, ok) {
    const p = form.querySelector(".pt-feedback");
    if (!p) return;

    p.hidden = false;
    p.textContent = msg;

    p.classList.remove("correct", "incorrect", "pt-feedback--ok", "pt-feedback--bad");
    p.classList.add(ok ? "correct" : "incorrect", ok ? "pt-feedback--ok" : "pt-feedback--bad");
  }

  function lockForm(form) {
    const inputs = form.querySelectorAll('input[type="radio"]');
    inputs.forEach((i) => (i.disabled = true));

    const btn = form.querySelector(".pt-check-answer");
    if (btn) {
      btn.disabled = true;
      btn.classList.add("pt-btn--disabled");
    }
  }

  function getSelectedValue(form) {
    const checked = form.querySelector('input[type="radio"]:checked');
    return checked ? String(checked.value || "").toUpperCase() : "";
  }

  function getCorrectValue(form) {
    return String(form.dataset.correct || "").trim().toUpperCase();
  }

  function getOptionText(form, value) {
    const input = form.querySelector('input[type="radio"][value="' + value + '"]');
    const label = input ? input.closest(".ls-option") : null;
    if (!label) return "";
    return String(label.textContent || "")
      .replace(/^\s*[A-D]\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function getCSRFToken() {
    const el = document.getElementById("csrf-token");
    return el ? el.value : "";
  }

  function updateProgressBar(data) {
    try {
      const doneEl = document.getElementById("ptProgressDone");
      const totalEl = document.getElementById("ptProgressTotal");
      const pctEl = document.getElementById("ptProgressPct");
      const fillEl = document.getElementById("ptProgressFill");

      if (doneEl) doneEl.textContent = String(data.completed_exercises ?? "");
      if (totalEl) totalEl.textContent = String(data.total_exercises ?? "");
      if (pctEl) pctEl.textContent = String(data.percent ?? "");

      if (fillEl && typeof data.percent === "number") {
        fillEl.style.width = `${data.percent}%`;
        const bar = fillEl.closest(".ls-progress__track, .pt-progress-bar");
        if (bar) bar.setAttribute("aria-valuenow", String(data.percent));
      }
    } catch (e) {}
  }

  async function sendExerciseProgress({ exerciseId, selected, correct }) {
    const csrf = getCSRFToken();
    if (!csrf) return null;

    try {
      const res = await fetch("/prep/exercise-progress/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({
          exercise_id: exerciseId,
          selected,
          correct,
        }),
      });

      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  // ✅ UX: après validation, on propose de reload soft si besoin
  function softUnlockHint() {
    // Ici on ne fait rien de risqué.
    // Si tu veux ensuite : animation, scroll next, toast.
  }

  document.addEventListener("click", async function (e) {
    const btn = e.target.closest ? e.target.closest(".pt-check-answer") : null;
    if (!btn) return;

    const form = closest(btn, ".pt-exercise-form");
    if (!form) return;

    if (form.dataset.locked === "1") return;

    const selected = getSelectedValue(form);
    const correctVal = getCorrectValue(form);

    if (!selected) {
      setFeedback(form, "⚠️ Choisis une réponse avant de vérifier.", false);
      return;
    }

    if (!correctVal) {
      setFeedback(form, "⚠️ Erreur interne: data-correct manquant.", false);
      return;
    }

    const ok = selected === correctVal;

    if (ok) {
      const selectedText = getOptionText(form, selected);
      setFeedback(
        form,
        "✅ Bonne réponse !" + (selectedText ? " Réponse : " + selected + " — " + selectedText : ""),
        true
      );
    } else {
      const correctText = getOptionText(form, correctVal);
      setFeedback(
        form,
        "❌ Mauvaise réponse. Bonne réponse : " + correctVal + (correctText ? " — " + correctText : "") + ".",
        false
      );
    }

    form.querySelectorAll(".ls-option").forEach(function (label) {
      const input = label.querySelector('input[type="radio"]');
      const value = input ? String(input.value || "").toUpperCase() : "";
      label.classList.toggle("is-correct", value === correctVal);
      label.classList.toggle("is-incorrect", value === selected && selected !== correctVal);
    });

    form.dataset.locked = "1";
    lockForm(form);

    const exerciseId = parseInt(form.dataset.exerciseId || "0", 10);
    if (exerciseId) {
      btn.disabled = true;
      const data = await sendExerciseProgress({
        exerciseId,
        selected,
        correct: ok,
      });

      if (data && data.ok) {
        updateProgressBar(data);
        if (data.explanation) {
          const answerText = data.correct_text || getOptionText(form, data.correct_option || correctVal);
          setFeedback(
            form,
            (data.correct ? "✅ Bonne réponse !" : "❌ Mauvaise réponse.")
              + " Bonne réponse : " + (data.correct_option || correctVal)
              + (answerText ? " — " + answerText : "")
              + ". Pourquoi : " + data.explanation,
            data.correct
          );
        }
        softUnlockHint();
      }
    }
  });

  // ================================================================
  // 🎤 MODULE EO — Enregistreur audio + soumission IA
  // ================================================================

  var mediaRecorder = null;
  var audioChunks = [];
  var audioBlob = null;
  var recordTimerInterval = null;
  var recordSeconds = 0;

  function formatTime(s) {
    var m = Math.floor(s / 60);
    var sec = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (sec < 10 ? "0" : "") + sec;
  }

  function startTimer(timerEl) {
    recordSeconds = 0;
    timerEl.textContent = "⏱ 00:00";
    recordTimerInterval = setInterval(function () {
      recordSeconds++;
      timerEl.textContent = "⏱ " + formatTime(recordSeconds);
    }, 1000);
  }

  function stopTimer() {
    if (recordTimerInterval) {
      clearInterval(recordTimerInterval);
      recordTimerInterval = null;
    }
  }

  function displayEOResult(container, data) {
    var scoreColor = data.score >= 70 ? "#22c55e" : data.score >= 50 ? "#f59e0b" : "#ef4444";
    var pointsHtml = (data.points_covered || [])
      .map(function (p) { return "<li>" + escapeHtml(p) + "</li>"; })
      .join("");
    var suggestionsHtml = (data.suggestions || [])
      .map(function (s) { return "<li>" + escapeHtml(s) + "</li>"; })
      .join("");

    container.innerHTML =
      '<div class="pt-result-card">' +
        '<div class="pt-score-badge" style="background:' + scoreColor + '">' +
          Math.round(data.score) + "/100" +
        "</div>" +
        '<p class="pt-result-feedback">' + escapeHtml(data.feedback || "") + "</p>" +
        (data.transcript
          ? '<div class="pt-result-section">' +
              '<h4>📝 Transcription</h4>' +
              '<p class="pt-transcript">' + escapeHtml(data.transcript) + "</p>" +
            "</div>"
          : "") +
        (pointsHtml
          ? '<div class="pt-result-section">' +
              "<h4>✅ Points abordés</h4><ul>" + pointsHtml + "</ul>" +
            "</div>"
          : "") +
        (suggestionsHtml
          ? '<div class="pt-result-section">' +
              "<h4>💡 Suggestions</h4><ul>" + suggestionsHtml + "</ul>" +
            "</div>"
          : "") +
      "</div>";
    container.style.display = "block";
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Délégation : click sur .pt-record-btn
  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".pt-record-btn") : null;
    if (!btn) return;

    var card = btn.closest(".pt-eo-card");
    if (!card) return;
    var timerEl = card.querySelector(".pt-record-timer");
    var playback = card.querySelector(".pt-playback");
    var submitBtn = card.querySelector(".pt-submit-eo");

    if (mediaRecorder && mediaRecorder.state === "recording") {
      // STOP
      mediaRecorder.stop();
      stopTimer();
      btn.textContent = "🎤 Recommencer";
      btn.classList.remove("pt-record-btn--recording");
      return;
    }

    // START
    audioChunks = [];
    audioBlob = null;
    if (playback) {
      playback.src = "";
      playback.style.display = "none";
    }
    if (submitBtn) submitBtn.disabled = true;

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then(function (stream) {
        var mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });

        mediaRecorder.ondataavailable = function (ev) {
          if (ev.data && ev.data.size > 0) audioChunks.push(ev.data);
        };

        mediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          audioBlob = new Blob(audioChunks, { type: mimeType });
          if (playback) {
            playback.src = URL.createObjectURL(audioBlob);
            playback.style.display = "block";
          }
          if (submitBtn) submitBtn.disabled = false;
        };

        mediaRecorder.start();
        startTimer(timerEl);
        btn.textContent = "⏹️ Arrêter l'enregistrement";
        btn.classList.add("pt-record-btn--recording");
      })
      .catch(function (err) {
        if (timerEl) timerEl.textContent = "⚠️ Micro non disponible";
        console.error("Microphone error:", err);
      });
  });

  // Délégation : click sur .pt-submit-eo
  document.addEventListener("click", async function (e) {
    var btn = e.target.closest ? e.target.closest(".pt-submit-eo") : null;
    if (!btn) return;
    if (btn.disabled) return;

    var card = btn.closest(".pt-eo-card");
    if (!card) return;
    var exerciseId = card.dataset.exerciseId;
    var resultEl = card.querySelector(".pt-eo-result");

    if (!audioBlob) {
      if (resultEl) {
        resultEl.innerHTML = '<p class="pt-feedback--bad">⚠️ Enregistre d\'abord ta réponse.</p>';
        resultEl.style.display = "block";
      }
      return;
    }

    btn.disabled = true;
    btn.textContent = "⏳ Analyse en cours…";

    var csrf = getCSRFToken();
    var formData = new FormData();
    formData.append("exercise_id", exerciseId);
    formData.append("audio", audioBlob, "recording.webm");

    try {
      var res = await fetch("/prep/api/submit-eo/", {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
        body: formData,
      });
      var data = await res.json();

      if (data.ok && resultEl) {
        displayEOResult(resultEl, data);
        updateProgressBar(data);
        btn.textContent = "✅ Soumis";
      } else {
        if (resultEl) {
          resultEl.innerHTML =
            '<p class="pt-feedback--bad">❌ Erreur : ' + escapeHtml(data.error || "inconnue") + "</p>";
          resultEl.style.display = "block";
        }
        btn.disabled = false;
        btn.textContent = "📤 Soumettre pour évaluation IA";
      }
    } catch (err) {
      if (resultEl) {
        resultEl.innerHTML = '<p class="pt-feedback--bad">❌ Erreur réseau. Réessaie.</p>';
        resultEl.style.display = "block";
      }
      btn.disabled = false;
      btn.textContent = "📤 Soumettre pour évaluation IA";
    }
  });

  // ================================================================
  // ✍️ MODULE EE — Compteur de mots + soumission IA
  // ================================================================

  // Compteur de mots en temps réel
  document.addEventListener("input", function (e) {
    var textarea = e.target.closest ? e.target.closest(".pt-ee-textarea") : null;
    if (!textarea) return;
    var card = textarea.closest(".pt-ee-card");
    if (!card) return;
    var counter = card.querySelector(".pt-word-count");
    if (!counter) return;
    var words = textarea.value.trim().split(/\s+/).filter(Boolean).length;
    counter.textContent = String(words);
  });

  // Soumission EE
  document.addEventListener("click", async function (e) {
    var btn = e.target.closest ? e.target.closest(".pt-submit-ee") : null;
    if (!btn) return;
    if (btn.disabled) return;

    var card = btn.closest(".pt-ee-card");
    if (!card) return;
    var exerciseId = card.dataset.exerciseId;
    var textarea = card.querySelector(".pt-ee-textarea");
    var resultEl = card.querySelector(".pt-ee-result");
    var text = textarea ? textarea.value.trim() : "";

    if (!text) {
      if (resultEl) {
        resultEl.innerHTML = '<p class="pt-feedback--bad">⚠️ Rédige ta réponse avant de soumettre.</p>';
        resultEl.style.display = "block";
      }
      return;
    }

    btn.disabled = true;
    btn.textContent = "⏳ Correction en cours…";

    var csrf = getCSRFToken();

    try {
      var res = await fetch("/prep/api/submit-ee/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ exercise_id: parseInt(exerciseId, 10), text: text }),
      });
      var data = await res.json();

      if (data.ok && resultEl) {
        displayEEResult(resultEl, data);
        updateProgressBar(data);
        btn.textContent = "✅ Soumis";
        if (textarea) textarea.readOnly = true;
      } else {
        if (resultEl) {
          resultEl.innerHTML =
            '<p class="pt-feedback--bad">❌ Erreur : ' + escapeHtml(data.error || "inconnue") + "</p>";
          resultEl.style.display = "block";
        }
        btn.disabled = false;
        btn.textContent = "✅ Soumettre pour correction IA";
      }
    } catch (err) {
      if (resultEl) {
        resultEl.innerHTML = '<p class="pt-feedback--bad">❌ Erreur réseau. Réessaie.</p>';
        resultEl.style.display = "block";
      }
      btn.disabled = false;
      btn.textContent = "✅ Soumettre pour correction IA";
    }
  });

  function displayEEResult(container, data) {
    var scoreColor = data.score >= 70 ? "#22c55e" : data.score >= 50 ? "#f59e0b" : "#ef4444";
    var errorsHtml = (data.errors || [])
      .map(function (err) {
        return (
          '<li class="pt-error-item">' +
            '<span class="pt-error-original">' + escapeHtml(err.original || "") + "</span>" +
            " → " +
            '<span class="pt-error-correction">' + escapeHtml(err.correction || "") + "</span>" +
            (err.rule ? ' <em class="pt-error-rule">(' + escapeHtml(err.rule) + ")</em>" : "") +
          "</li>"
        );
      })
      .join("");

    container.innerHTML =
      '<div class="pt-result-card">' +
        '<div class="pt-score-badge" style="background:' + scoreColor + '">' +
          Math.round(data.score) + "/100" +
        "</div>" +
        "<p>" + String(data.word_count || 0) + " mots rédigés</p>" +
        '<p class="pt-result-feedback">' + escapeHtml(data.feedback || "") + "</p>" +
        (errorsHtml
          ? '<div class="pt-result-section">' +
              "<h4>🔍 Corrections</h4><ul>" + errorsHtml + "</ul>" +
            "</div>"
          : "") +
        (data.corrected_version
          ? '<div class="pt-result-section">' +
              "<h4>✅ Version corrigée</h4>" +
              '<pre class="pt-corrected-version">' + escapeHtml(data.corrected_version) + "</pre>" +
            "</div>"
          : "") +
      "</div>";
    container.style.display = "block";
  }

})();
