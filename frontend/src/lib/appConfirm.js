let confirmHandler = null;

export function registerAppConfirm(handler) {
  confirmHandler = handler;
  return () => {
    if (confirmHandler === handler) confirmHandler = null;
  };
}

export function appConfirm(options) {
  if (!confirmHandler) return Promise.resolve(false);
  const normalized = typeof options === "string" ? { message: options } : (options || {});
  return confirmHandler(normalized);
}
