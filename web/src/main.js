import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./styles.css";
import "./styles/student-base.css";
import "./styles/student-pages.css";
import "./styles/student-redesign.css";
import "./styles/student-home.css";
import "./styles/teacher-base.css";
import "./styles/teacher-pages.css";

createApp(App).use(createPinia()).use(router).mount("#app");
