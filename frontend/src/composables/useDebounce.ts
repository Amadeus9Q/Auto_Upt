import { ref } from "vue";

/** 可复用的 debounce 工具 composable */
export function useDebounce(delay = 300) {
  const timer = ref<number | null>(null);

  function debounce(fn: () => void) {
    if (timer.value !== null) clearTimeout(timer.value);
    timer.value = window.setTimeout(fn, delay);
  }

  function cancel() {
    if (timer.value !== null) {
      clearTimeout(timer.value);
      timer.value = null;
    }
  }

  return { debounce, cancel };
}
