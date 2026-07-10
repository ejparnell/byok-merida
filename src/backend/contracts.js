export const OPERATOR_FAILURE_REASONS = {
  INVALID_TOKEN: "invalid_token",
  INVALID_REQUEST: "invalid_request",
};

export function failed(reason, message, extra = {}) {
  return {
    type: "failed",
    reason,
    message,
    ...extra,
  };
}
