import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./styles.css";
import "./styles/student-base.css";
import "./styles/student-pages.css";
import "./styles/student-redesign.css";
import "./styles/student-community.css";
import "./styles/student-home.css";
import "./styles/student-profile-reference.css";
import "./styles/counselor-reference.css";
import "./styles/study-reference.css";
import "./styles/study-secondary.css";

createApp(App).use(createPinia()).use(router).mount("#app");
