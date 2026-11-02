import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Overview from './views/Overview.vue'
import Fuel from './views/Fuel.vue'
import Maintenance from './views/Maintenance.vue'
import Costs from './views/Costs.vue'
import Vehicles from './views/Vehicles.vue'
import Settings from './views/Settings.vue'
import './style.css'

// Hash history: Ingress serves the app under a path we do not control.
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Overview },
    { path: '/fuel', component: Fuel },
    { path: '/maintenance', component: Maintenance },
    { path: '/costs', component: Costs },
    { path: '/vehicles', component: Vehicles },
    { path: '/settings', component: Settings },
  ],
})

createApp(App).use(router).mount('#app')
