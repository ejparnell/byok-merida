import type { ApiErrorDetail } from './generated/types.gen'

type OperatorApiError = Error & {
  code?: ApiErrorDetail['code']
  requestId?: string | null
  validationFailures?: unknown[]
}

export const toOperatorError = (error: unknown): OperatorApiError => {
  if (error instanceof Error) return error

  const payload = error as {
    error?: { code?: ApiErrorDetail['code']; message?: string; requestId?: string | null }
    errors?: string[]
    validationFailures?: unknown[]
  }
  const operatorError = new Error(
    payload?.error?.message || payload?.errors?.[0] || 'The API request failed.',
  ) as OperatorApiError
  operatorError.code = payload?.error?.code
  operatorError.requestId = payload?.error?.requestId
  operatorError.validationFailures = payload?.validationFailures
  return operatorError
}

export const invokeApi = async <T>(request: Promise<T>): Promise<T> => {
  try {
    return await request
  } catch (error) {
    throw toOperatorError(error)
  }
}

// Hey API's generated SDK currently types configured `responseStyle: "data"`
// clients as field-style results. Keep that generator mismatch inside the
// shared client package so both consumers still receive generated response
// types at their public seams.
export const invokeData = async <T>(request: Promise<unknown>): Promise<T> =>
  invokeApi(request) as Promise<T>
