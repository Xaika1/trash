const form = document.getElementById("form");
const heading = document.getElementById("heading");
const submit = document.getElementById("submit");
const switchLink = document.getElementById("switch");
const confirmRow = document.getElementById("confirm-row");
const passwordInput = document.getElementById("password");
const errorText = document.getElementById("error");

let registering = false;

function getNextPage() {
  const next = new URLSearchParams(location.search).get("next");
  if (next && next.startsWith("/") && !next.startsWith("//")) {
    return next;
  }
  return "/";
}

function setMode(register) {
  registering = register;
  heading.textContent = register ? "Регистрация" : "Вход";
  submit.textContent = register ? "Зарегистрироваться" : "Войти";
  switchLink.textContent = register ? "Уже есть аккаунт? Войти" : "Нет аккаунта? Зарегистрироваться";
  confirmRow.hidden = !register;
  passwordInput.autocomplete = register ? "new-password" : "current-password";
  errorText.textContent = "";
}

switchLink.addEventListener("click", (event) => {
  event.preventDefault();
  setMode(!registering);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorText.textContent = "";

  const body = {
    login: document.getElementById("login").value.trim(),
    password: passwordInput.value,
    password_confirm: document.getElementById("password-confirm").value,
  };

  const response = await fetch(registering ? "/api/register" : "/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (response.ok) {
    location.href = getNextPage();
    return;
  }

  const data = await response.json().catch(() => ({}));
  errorText.textContent = typeof data.detail === "string" ? data.detail : "Проверьте введённые данные";
});
