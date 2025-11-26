const DEFAULT_URL = "";

async function request(endpoint: string, method: string = "get", data?: any) {
  const url = `${DEFAULT_URL}/api/${endpoint}`;

  const options: RequestInit = {
    method: method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Telegram-Init-Data": data?.initDataRaw || "",
    },
    body: data
      ? JSON.stringify({
          ...(data.user_id && { user_id: data.user_id }),
          ...(data.cards && { cards: data.cards }),
          ...(data.message_id && { message_id: data.message_id }),
        })
      : undefined,
    // Добавляем keepalive для гарантированной отправки
    keepalive: true,
  };

  try {
    const response = await fetch(url, options);
    const jsonData = await response.json();

    if (response.ok) {
      return jsonData;
    }

    throw new Error(jsonData.message || "Request failed");
  } catch (error) {
    console.error("Ошибка запроса:", error);
    throw error;
  }
}

export default request;
