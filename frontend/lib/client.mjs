// Never retry automatically: a failed response can still have created a run.
export async function api(path, body, signal, fetcher = fetch) {
  let response;
  try {
    response = await fetcher(`/api/backend/${path}`, {
      method: body ? "POST" : "GET",
      cache: "no-store",
      signal,
      ...(body ? {
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      } : {}),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw Error("Connection interrupted. Your current view and draft are retained. " +
      (body ? "The request may have completed; check History before submitting again." : "Check the connection before trying again."));
  }
  let value;
  try {
    value = await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw Error("The service returned an unreadable response. Your current view and draft are retained." +
      (body ? " The request may have completed; check History before submitting again." : ""));
  }
  if (!response.ok) {
    throw Error(typeof value.detail === "string" ? value.detail :
      response.status === 401 || response.status === 403
        ? "Private access is required. You can still explore the preserved research stories."
        : "The request could not complete. Check your selections and connection.");
  }
  return value;
}
