import { computed, ref } from "vue";
import {
  fetchAuthConfig,
  fetchWhoami,
  login as apiLogin,
  logout as apiLogout,
  type AuthUser,
} from "../auth/session";

const requireAuth = ref(true);
const sttEnabledForMe = ref(true);
const sttUsers = ref<string[]>([]);
const freeChatEnabledForMe = ref(false);
const freeChatUsers = ref<string[]>([]);
const user = ref<AuthUser | null>(null);
const authReady = ref(false);
const authError = ref("");

export function useAuth() {
  const isAuthenticated = computed(() => Boolean(user.value));
  const displayName = computed(
    () => user.value?.display_name || user.value?.username || "",
  );

  async function refreshAuth() {
    authError.value = "";
    const cfg = await fetchAuthConfig();
    requireAuth.value = cfg.require_auth;
    sttUsers.value = cfg.stt_users ?? [];
    freeChatUsers.value = cfg.free_chat_users ?? [];
    if (!cfg.require_auth) {
      user.value = null;
      sttEnabledForMe.value = cfg.stt_enabled_for_me;
      freeChatEnabledForMe.value = cfg.free_chat_enabled_for_me;
      authReady.value = true;
      return;
    }
    const who = await fetchWhoami();
    if (who.authenticated && who.user_id && who.username) {
      user.value = {
        user_id: who.user_id,
        username: who.username,
        display_name: who.display_name || who.username,
      };
    } else {
      user.value = null;
    }
    sttEnabledForMe.value = cfg.stt_enabled_for_me;
    freeChatEnabledForMe.value = cfg.free_chat_enabled_for_me;
    authReady.value = true;
  }

  async function login(username: string, password: string) {
    authError.value = "";
    const u = await apiLogin(username, password);
    user.value = {
      user_id: u.user_id,
      username: u.username,
      display_name: u.display_name || u.username,
    };
    const cfg = await fetchAuthConfig();
    sttEnabledForMe.value = cfg.stt_enabled_for_me;
    sttUsers.value = cfg.stt_users ?? [];
    freeChatEnabledForMe.value = cfg.free_chat_enabled_for_me;
    freeChatUsers.value = cfg.free_chat_users ?? [];
  }

  async function logout() {
    authError.value = "";
    await apiLogout();
    user.value = null;
    const cfg = await fetchAuthConfig();
    sttEnabledForMe.value = cfg.stt_enabled_for_me;
    sttUsers.value = cfg.stt_users ?? [];
    freeChatEnabledForMe.value = cfg.free_chat_enabled_for_me;
    freeChatUsers.value = cfg.free_chat_users ?? [];
  }

  return {
    requireAuth,
    sttEnabledForMe,
    sttUsers,
    freeChatEnabledForMe,
    freeChatUsers,
    user,
    authReady,
    authError,
    isAuthenticated,
    displayName,
    refreshAuth,
    login,
    logout,
  };
}
