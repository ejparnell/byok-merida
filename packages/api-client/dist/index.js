//#region src/generated/core/bodySerializer.gen.ts
var jsonBodySerializer = { bodySerializer: (body) => JSON.stringify(body, (_key, value) => typeof value === "bigint" ? value.toString() : value) };
Object.entries({
	$body_: "body",
	$headers_: "headers",
	$path_: "path",
	$query_: "query"
});
//#endregion
//#region src/generated/core/serverSentEvents.gen.ts
function createSseClient({ onRequest, onSseError, onSseEvent, responseTransformer, responseValidator, sseDefaultRetryDelay, sseMaxRetryAttempts, sseMaxRetryDelay, sseSleepFn, url, ...options }) {
	let lastEventId;
	const sleep = sseSleepFn ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
	const createStream = async function* () {
		let retryDelay = sseDefaultRetryDelay ?? 3e3;
		let attempt = 0;
		const signal = options.signal ?? new AbortController().signal;
		while (true) {
			if (signal.aborted) break;
			attempt++;
			const headers = options.headers instanceof Headers ? options.headers : new Headers(options.headers);
			if (lastEventId !== void 0) headers.set("Last-Event-ID", lastEventId);
			try {
				const requestInit = {
					redirect: "follow",
					...options,
					body: options.serializedBody,
					headers,
					signal
				};
				let request = new Request(url, requestInit);
				if (onRequest) request = await onRequest(url, requestInit);
				const response = await (options.fetch ?? globalThis.fetch)(request);
				if (!response.ok) throw new Error(`SSE failed: ${response.status} ${response.statusText}`);
				if (!response.body) throw new Error("No body in SSE response");
				const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
				let buffer = "";
				const abortHandler = () => {
					try {
						reader.cancel();
					} catch {}
				};
				signal.addEventListener("abort", abortHandler);
				try {
					while (true) {
						const { done, value } = await reader.read();
						if (done) break;
						buffer += value;
						buffer = buffer.replace(/\r\n?/g, "\n");
						const chunks = buffer.split("\n\n");
						buffer = chunks.pop() ?? "";
						for (const chunk of chunks) {
							const lines = chunk.split("\n");
							const dataLines = [];
							let eventName;
							for (const line of lines) if (line.startsWith("data:")) dataLines.push(line.replace(/^data:\s*/, ""));
							else if (line.startsWith("event:")) eventName = line.replace(/^event:\s*/, "");
							else if (line.startsWith("id:")) lastEventId = line.replace(/^id:\s*/, "");
							else if (line.startsWith("retry:")) {
								const parsed = Number.parseInt(line.replace(/^retry:\s*/, ""), 10);
								if (!Number.isNaN(parsed)) retryDelay = parsed;
							}
							let data;
							let parsedJson = false;
							if (dataLines.length) {
								const rawData = dataLines.join("\n");
								try {
									data = JSON.parse(rawData);
									parsedJson = true;
								} catch {
									data = rawData;
								}
							}
							if (parsedJson) {
								if (responseValidator) await responseValidator(data);
								if (responseTransformer) data = await responseTransformer(data);
							}
							onSseEvent?.({
								data,
								event: eventName,
								id: lastEventId,
								retry: retryDelay
							});
							if (dataLines.length) yield data;
						}
					}
				} finally {
					signal.removeEventListener("abort", abortHandler);
					reader.releaseLock();
				}
				break;
			} catch (error) {
				onSseError?.(error);
				if (sseMaxRetryAttempts !== void 0 && attempt >= sseMaxRetryAttempts) break;
				const backoff = Math.min(retryDelay * 2 ** (attempt - 1), sseMaxRetryDelay ?? 3e4);
				await sleep(backoff);
			}
		}
	};
	return { stream: createStream() };
}
//#endregion
//#region src/generated/core/pathSerializer.gen.ts
var separatorArrayExplode = (style) => {
	switch (style) {
		case "label": return ".";
		case "matrix": return ";";
		case "simple": return ",";
		default: return "&";
	}
};
var separatorArrayNoExplode = (style) => {
	switch (style) {
		case "form": return ",";
		case "pipeDelimited": return "|";
		case "spaceDelimited": return "%20";
		default: return ",";
	}
};
var separatorObjectExplode = (style) => {
	switch (style) {
		case "label": return ".";
		case "matrix": return ";";
		case "simple": return ",";
		default: return "&";
	}
};
var serializeArrayParam = ({ allowReserved, explode, name, style, value }) => {
	if (!explode) {
		const joinedValues = (allowReserved ? value : value.map((v) => encodeURIComponent(v))).join(separatorArrayNoExplode(style));
		switch (style) {
			case "label": return `.${joinedValues}`;
			case "matrix": return `;${name}=${joinedValues}`;
			case "simple": return joinedValues;
			default: return `${name}=${joinedValues}`;
		}
	}
	const separator = separatorArrayExplode(style);
	const joinedValues = value.map((v) => {
		if (style === "label" || style === "simple") return allowReserved ? v : encodeURIComponent(v);
		return serializePrimitiveParam({
			allowReserved,
			name,
			value: v
		});
	}).join(separator);
	return style === "label" || style === "matrix" ? separator + joinedValues : joinedValues;
};
var serializePrimitiveParam = ({ allowReserved, name, value }) => {
	if (value === void 0 || value === null) return "";
	if (typeof value === "object") throw new Error("Deeply-nested arrays/objects aren’t supported. Provide your own `querySerializer()` to handle these.");
	return `${name}=${allowReserved ? value : encodeURIComponent(value)}`;
};
var serializeObjectParam = ({ allowReserved, explode, name, style, value, valueOnly }) => {
	if (value instanceof Date) return valueOnly ? value.toISOString() : `${name}=${value.toISOString()}`;
	if (style !== "deepObject" && !explode) {
		let values = [];
		Object.entries(value).forEach(([key, v]) => {
			values = [
				...values,
				key,
				allowReserved ? v : encodeURIComponent(v)
			];
		});
		const joinedValues = values.join(",");
		switch (style) {
			case "form": return `${name}=${joinedValues}`;
			case "label": return `.${joinedValues}`;
			case "matrix": return `;${name}=${joinedValues}`;
			default: return joinedValues;
		}
	}
	const separator = separatorObjectExplode(style);
	const joinedValues = Object.entries(value).map(([key, v]) => serializePrimitiveParam({
		allowReserved,
		name: style === "deepObject" ? `${name}[${key}]` : key,
		value: v
	})).join(separator);
	return style === "label" || style === "matrix" ? separator + joinedValues : joinedValues;
};
//#endregion
//#region src/generated/core/utils.gen.ts
var PATH_PARAM_RE = /\{[^{}]+\}/g;
var defaultPathSerializer = ({ path, url: _url }) => {
	let url = _url;
	const matches = _url.match(PATH_PARAM_RE);
	if (matches) for (const match of matches) {
		let explode = false;
		let name = match.substring(1, match.length - 1);
		let style = "simple";
		if (name.endsWith("*")) {
			explode = true;
			name = name.substring(0, name.length - 1);
		}
		if (name.startsWith(".")) {
			name = name.substring(1);
			style = "label";
		} else if (name.startsWith(";")) {
			name = name.substring(1);
			style = "matrix";
		}
		const value = path[name];
		if (value === void 0 || value === null) continue;
		if (Array.isArray(value)) {
			url = url.replace(match, serializeArrayParam({
				explode,
				name,
				style,
				value
			}));
			continue;
		}
		if (typeof value === "object") {
			url = url.replace(match, serializeObjectParam({
				explode,
				name,
				style,
				value,
				valueOnly: true
			}));
			continue;
		}
		if (style === "matrix") {
			url = url.replace(match, `;${serializePrimitiveParam({
				name,
				value
			})}`);
			continue;
		}
		const replaceValue = encodeURIComponent(style === "label" ? `.${value}` : value);
		url = url.replace(match, replaceValue);
	}
	return url;
};
var getUrl = ({ baseUrl, path, query, querySerializer, url: _url }) => {
	const pathUrl = _url.startsWith("/") ? _url : `/${_url}`;
	let url = (baseUrl ?? "") + pathUrl;
	if (path) url = defaultPathSerializer({
		path,
		url
	});
	let search = query ? querySerializer(query) : "";
	if (search.startsWith("?")) search = search.substring(1);
	if (search) url += `?${search}`;
	return url;
};
function getValidRequestBody(options) {
	const hasBody = options.body !== void 0;
	if (hasBody && options.bodySerializer) {
		if ("serializedBody" in options) return options.serializedBody !== void 0 && options.serializedBody !== "" ? options.serializedBody : null;
		return options.body !== "" ? options.body : null;
	}
	if (hasBody) return options.body;
}
//#endregion
//#region src/generated/core/auth.gen.ts
var getAuthToken = async (auth, callback) => {
	const token = typeof callback === "function" ? await callback(auth) : callback;
	if (!token) return;
	if (auth.scheme === "bearer") return `Bearer ${token}`;
	if (auth.scheme === "basic") return `Basic ${btoa(token)}`;
	return token;
};
//#endregion
//#region src/generated/client/utils.gen.ts
var createQuerySerializer = ({ parameters = {}, ...args } = {}) => {
	const querySerializer = (queryParams) => {
		const search = [];
		if (queryParams && typeof queryParams === "object") for (const name in queryParams) {
			const value = queryParams[name];
			if (value === void 0 || value === null) continue;
			const options = parameters[name] || args;
			if (Array.isArray(value)) {
				const serializedArray = serializeArrayParam({
					allowReserved: options.allowReserved,
					explode: true,
					name,
					style: "form",
					value,
					...options.array
				});
				if (serializedArray) search.push(serializedArray);
			} else if (typeof value === "object") {
				const serializedObject = serializeObjectParam({
					allowReserved: options.allowReserved,
					explode: true,
					name,
					style: "deepObject",
					value,
					...options.object
				});
				if (serializedObject) search.push(serializedObject);
			} else {
				const serializedPrimitive = serializePrimitiveParam({
					allowReserved: options.allowReserved,
					name,
					value
				});
				if (serializedPrimitive) search.push(serializedPrimitive);
			}
		}
		return search.join("&");
	};
	return querySerializer;
};
/**
* Infers parseAs value from provided Content-Type header.
*/
var getParseAs = (contentType) => {
	if (!contentType) return "stream";
	const cleanContent = contentType.split(";")[0]?.trim();
	if (!cleanContent) return;
	if (cleanContent.startsWith("application/json") || cleanContent.endsWith("+json")) return "json";
	if (cleanContent === "multipart/form-data") return "formData";
	if ([
		"application/",
		"audio/",
		"image/",
		"video/"
	].some((type) => cleanContent.startsWith(type))) return "blob";
	if (cleanContent.startsWith("text/")) return "text";
};
var checkForExistence = (options, name) => {
	if (!name) return false;
	if (options.headers.has(name) || options.query?.[name] || options.headers.get("Cookie")?.includes(`${name}=`)) return true;
	return false;
};
async function setAuthParams(options) {
	for (const auth of options.security ?? []) {
		if (checkForExistence(options, auth.name)) continue;
		const token = await getAuthToken(auth, options.auth);
		if (!token) continue;
		const name = auth.name ?? "Authorization";
		switch (auth.in) {
			case "query":
				if (!options.query) options.query = {};
				options.query[name] = token;
				break;
			case "cookie":
				options.headers.append("Cookie", `${name}=${token}`);
				break;
			default:
				options.headers.set(name, token);
				break;
		}
	}
}
var buildUrl = (options) => getUrl({
	baseUrl: options.baseUrl,
	path: options.path,
	query: options.query,
	querySerializer: typeof options.querySerializer === "function" ? options.querySerializer : createQuerySerializer(options.querySerializer),
	url: options.url
});
var mergeConfigs = (a, b) => {
	const config = {
		...a,
		...b
	};
	if (config.baseUrl?.endsWith("/")) config.baseUrl = config.baseUrl.substring(0, config.baseUrl.length - 1);
	config.headers = mergeHeaders(a.headers, b.headers);
	return config;
};
var headersEntries = (headers) => {
	const entries = [];
	headers.forEach((value, key) => {
		entries.push([key, value]);
	});
	return entries;
};
var mergeHeaders = (...headers) => {
	const mergedHeaders = new Headers();
	for (const header of headers) {
		if (!header) continue;
		const iterator = header instanceof Headers ? headersEntries(header) : Object.entries(header);
		for (const [key, value] of iterator) if (value === null) mergedHeaders.delete(key);
		else if (Array.isArray(value)) for (const v of value) mergedHeaders.append(key, v);
		else if (value !== void 0) mergedHeaders.set(key, typeof value === "object" ? JSON.stringify(value) : value);
	}
	return mergedHeaders;
};
var Interceptors = class {
	fns = [];
	clear() {
		this.fns = [];
	}
	eject(id) {
		const index = this.getInterceptorIndex(id);
		if (this.fns[index]) this.fns[index] = null;
	}
	exists(id) {
		const index = this.getInterceptorIndex(id);
		return Boolean(this.fns[index]);
	}
	getInterceptorIndex(id) {
		if (typeof id === "number") return this.fns[id] ? id : -1;
		return this.fns.indexOf(id);
	}
	update(id, fn) {
		const index = this.getInterceptorIndex(id);
		if (this.fns[index]) {
			this.fns[index] = fn;
			return id;
		}
		return false;
	}
	use(fn) {
		this.fns.push(fn);
		return this.fns.length - 1;
	}
};
var createInterceptors = () => ({
	error: new Interceptors(),
	request: new Interceptors(),
	response: new Interceptors()
});
var defaultQuerySerializer = createQuerySerializer({
	allowReserved: false,
	array: {
		explode: true,
		style: "form"
	},
	object: {
		explode: true,
		style: "deepObject"
	}
});
var defaultHeaders = { "Content-Type": "application/json" };
var createConfig = (override = {}) => ({
	...jsonBodySerializer,
	headers: defaultHeaders,
	parseAs: "auto",
	querySerializer: defaultQuerySerializer,
	...override
});
//#endregion
//#region src/generated/client/client.gen.ts
var createClient = (config = {}) => {
	let _config = mergeConfigs(createConfig(), config);
	const getConfig = () => ({ ..._config });
	const setConfig = (config) => {
		_config = mergeConfigs(_config, config);
		return getConfig();
	};
	const interceptors = createInterceptors();
	const beforeRequest = async (options) => {
		const opts = {
			..._config,
			...options,
			fetch: options.fetch ?? _config.fetch ?? globalThis.fetch,
			headers: mergeHeaders(_config.headers, options.headers),
			serializedBody: void 0
		};
		if (opts.security) await setAuthParams(opts);
		if (opts.requestValidator) await opts.requestValidator(opts);
		if (opts.body !== void 0 && opts.bodySerializer) opts.serializedBody = opts.bodySerializer(opts.body);
		if (opts.body === void 0 || opts.serializedBody === "") opts.headers.delete("Content-Type");
		const resolvedOpts = opts;
		return {
			opts: resolvedOpts,
			url: buildUrl(resolvedOpts)
		};
	};
	const request = async (options) => {
		const throwOnError = options.throwOnError ?? _config.throwOnError;
		const responseStyle = options.responseStyle ?? _config.responseStyle;
		let request;
		let response;
		try {
			const { opts, url } = await beforeRequest(options);
			const requestInit = {
				redirect: "follow",
				...opts,
				body: getValidRequestBody(opts)
			};
			request = new Request(url, requestInit);
			for (const fn of interceptors.request.fns) if (fn) request = await fn(request, opts);
			const _fetch = opts.fetch;
			response = await _fetch(request);
			for (const fn of interceptors.response.fns) if (fn) response = await fn(response, request, opts);
			const result = {
				request,
				response
			};
			if (response.ok) {
				const parseAs = (opts.parseAs === "auto" ? getParseAs(response.headers.get("Content-Type")) : opts.parseAs) ?? "json";
				if (response.status === 204 || response.headers.get("Content-Length") === "0") {
					let emptyData;
					switch (parseAs) {
						case "arrayBuffer":
						case "blob":
						case "text":
							emptyData = await response[parseAs]();
							break;
						case "formData":
							emptyData = new FormData();
							break;
						case "stream":
							emptyData = response.body;
							break;
						default:
							emptyData = {};
							break;
					}
					return opts.responseStyle === "data" ? emptyData : {
						data: emptyData,
						...result
					};
				}
				let data;
				switch (parseAs) {
					case "arrayBuffer":
					case "blob":
					case "formData":
					case "text":
						data = await response[parseAs]();
						break;
					case "json": {
						const text = await response.text();
						data = text ? JSON.parse(text) : {};
						break;
					}
					case "stream": return opts.responseStyle === "data" ? response.body : {
						data: response.body,
						...result
					};
				}
				if (parseAs === "json") {
					if (opts.responseValidator) await opts.responseValidator(data);
					if (opts.responseTransformer) data = await opts.responseTransformer(data);
				}
				return opts.responseStyle === "data" ? data : {
					data,
					...result
				};
			}
			const textError = await response.text();
			let jsonError;
			try {
				jsonError = JSON.parse(textError);
			} catch {}
			throw jsonError ?? textError;
		} catch (error) {
			let finalError = error;
			for (const fn of interceptors.error.fns) if (fn) finalError = await fn(finalError, response, request, options);
			finalError = finalError || {};
			if (throwOnError) throw finalError;
			return responseStyle === "data" ? void 0 : {
				error: finalError,
				request,
				response
			};
		}
	};
	const makeMethodFn = (method) => (options) => request({
		...options,
		method
	});
	const makeSseFn = (method) => async (options) => {
		const { opts, url } = await beforeRequest(options);
		return createSseClient({
			...opts,
			body: opts.body,
			method,
			onRequest: async (url, init) => {
				let request = new Request(url, init);
				for (const fn of interceptors.request.fns) if (fn) request = await fn(request, opts);
				return request;
			},
			serializedBody: getValidRequestBody(opts),
			url
		});
	};
	const _buildUrl = (options) => buildUrl({
		..._config,
		...options
	});
	return {
		buildUrl: _buildUrl,
		connect: makeMethodFn("CONNECT"),
		delete: makeMethodFn("DELETE"),
		get: makeMethodFn("GET"),
		getConfig,
		head: makeMethodFn("HEAD"),
		interceptors,
		options: makeMethodFn("OPTIONS"),
		patch: makeMethodFn("PATCH"),
		post: makeMethodFn("POST"),
		put: makeMethodFn("PUT"),
		request,
		setConfig,
		sse: {
			connect: makeSseFn("CONNECT"),
			delete: makeSseFn("DELETE"),
			get: makeSseFn("GET"),
			head: makeSseFn("HEAD"),
			options: makeSseFn("OPTIONS"),
			patch: makeSseFn("PATCH"),
			post: makeSseFn("POST"),
			put: makeSseFn("PUT"),
			trace: makeSseFn("TRACE")
		},
		trace: makeMethodFn("TRACE")
	};
};
//#endregion
//#region src/generated/client.gen.ts
var client = createClient(createConfig());
//#endregion
//#region src/generated/sdk.gen.ts
/**
* Get Analysis Queue
*/
var getApplicationAnalysisQueue = (options) => (options?.client ?? client).get({
	url: "/api/v1/applications/analysis/queue",
	...options
});
/**
* Run Application Analysis
*/
var runApplicationAnalysis = (options) => (options.client ?? client).post({
	url: "/api/v1/applications/analysis/run",
	...options,
	headers: {
		"Content-Type": "application/json",
		...options.headers
	}
});
/**
* Confirm Application
*/
var confirmApplication = (options) => (options.client ?? client).post({
	url: "/api/v1/applications/confirm",
	...options,
	headers: {
		"Content-Type": "application/json",
		...options.headers
	}
});
/**
* Prepare Application
*/
var prepareApplication = (options) => (options.client ?? client).post({
	url: "/api/v1/applications/prepare",
	...options,
	headers: {
		"Content-Type": "application/json",
		...options.headers
	}
});
/**
* Reset Demo
*/
var resetDemo = (options) => (options?.client ?? client).post({
	url: "/api/v1/demo/reset",
	...options
});
/**
* Get Health
*/
var getHealth = (options) => (options?.client ?? client).get({
	url: "/api/v1/health",
	...options
});
/**
* Get Analysis Health
*/
var getApplicationAnalysisHealth = (options) => (options?.client ?? client).get({
	url: "/api/v1/health/analysis",
	...options
});
/**
* Get Notion Health
*/
var getNotionHealth = (options) => (options?.client ?? client).get({
	url: "/api/v1/health/notion",
	...options
});
/**
* Get Resume Health
*/
var getResumeCreationHealth = (options) => (options?.client ?? client).get({
	url: "/api/v1/health/resumes",
	...options
});
/**
* Get Operator Settings
*/
var getOperatorSettings = (options) => (options?.client ?? client).get({
	url: "/api/v1/operator/settings",
	...options
});
/**
* Create Resume
*/
var createResume = (options) => (options.client ?? client).post({
	url: "/api/v1/resumes/create",
	...options,
	headers: {
		"Content-Type": "application/json",
		...options.headers
	}
});
/**
* Get Resume Queue
*/
var getResumeCreationQueue = (options) => (options?.client ?? client).get({
	url: "/api/v1/resumes/queue",
	...options
});
/**
* Download Resume Pdf
*/
var downloadResumePdf = (options) => (options.client ?? client).get({
	url: "/api/v1/resumes/{resumeId}/pdf",
	...options
});
//#endregion
//#region src/operatorError.ts
var toOperatorError = (error) => {
	if (error instanceof Error) return error;
	const payload = error;
	const operatorError = new Error(payload?.error?.message || payload?.errors?.[0] || "The API request failed.");
	operatorError.code = payload?.error?.code;
	operatorError.requestId = payload?.error?.requestId;
	operatorError.validationFailures = payload?.validationFailures;
	return operatorError;
};
var invokeApi = async (request) => {
	try {
		return await request;
	} catch (error) {
		throw toOperatorError(error);
	}
};
//#endregion
export { confirmApplication, createClient, createResume, downloadResumePdf, getApplicationAnalysisHealth, getApplicationAnalysisQueue, getHealth, getNotionHealth, getOperatorSettings, getResumeCreationHealth, getResumeCreationQueue, invokeApi, prepareApplication, resetDemo, runApplicationAnalysis, toOperatorError };

//# sourceMappingURL=index.js.map