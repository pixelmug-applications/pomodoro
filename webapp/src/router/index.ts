import { createRouter, createWebHashHistory } from 'vue-router';
import LandingView from '../views/LandingView.vue';
import PomodoroView from '../views/PomodoroView.vue';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingView },
    { path: '/timers', name: 'timers', component: PomodoroView },
  ],
});

export default router;
