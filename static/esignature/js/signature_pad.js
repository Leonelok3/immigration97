document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("signature-pad");
  if (!canvas) {
    return;
  }

  const signaturePad = new SignaturePad(canvas, {
    backgroundColor: "rgba(255,255,255,0)",
    penColor: "rgb(0, 0, 0)",
  });

  document.getElementById("clear-signature").addEventListener("click", function () {
    signaturePad.clear();
  });

  const form = document.getElementById("esignature-form");
  form.addEventListener("submit", function (event) {
    const acceptance = document.getElementById("acceptance").checked;
    const fullName = document.getElementById("full_name").value.trim();
    const signatureDataInput = document.getElementById("id_signature_data");
    const viewedInput = document.getElementById("id_viewed");

    if (!acceptance) {
      event.preventDefault();
      alert("Vous devez accepter le contrat pour continuer.");
      return;
    }

    if (!fullName) {
      event.preventDefault();
      alert("Merci de renseigner votre nom complet.");
      return;
    }

    if (signaturePad.isEmpty()) {
      event.preventDefault();
      alert("Veuillez signer le document avant de valider.");
      return;
    }

    const signatureData = signaturePad.toDataURL("image/png");
    signatureDataInput.value = signatureData;
    viewedInput.value = "true";
  });
});
