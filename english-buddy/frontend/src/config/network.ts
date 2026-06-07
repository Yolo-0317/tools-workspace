/** REST 请求超时（慢网/弱网避免无限挂起） */
export const API_FETCH_TIMEOUT_MS = 20_000;

/** WebSocket 握手超时 */
export const WS_CONNECT_TIMEOUT_MS = 15_000;

/** 已提交跟读/聊天但久未收到服务端回应时自动解锁 */
export const UTTERANCE_STUCK_TIMEOUT_MS = 12_000;
