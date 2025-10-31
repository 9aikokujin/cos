export const validateSocialUrl = (value, type) => {
  if (!value) return true;

  const trimmedValue = value.trim();

  try {
    new URL(trimmedValue);
  } catch {
    return "Введите корректный URL";
  }

  switch (type) {
    case "instagram":
      if (!trimmedValue.includes("instagram.com/")) {
        return "URL должен содержать instagram.com/";
      }
      break;
    case "tiktok":
      if (!trimmedValue.includes("tiktok.com/")) {
        return "URL должен содержать tiktok.com/";
      }
      break;
    case "youtube":
      if (!trimmedValue.includes("youtube.com/") && !trimmedValue.includes("youtu.be/")) {
        return "URL должен содержать youtube.com/ или youtu.be/";
      }
      break;
    case "likee":
      if (!trimmedValue.includes("l.likee.video/p/")) {
        return "URL должен содержать l.likee.video/p/";
      }
      break;
    default:
      return true;
  }

  return true;
};

export const sanitizeTikTokUrl = (url) => {
  try {
    const u = new URL(url);

    if (!u.hostname.includes("tiktok.com")) return url;

    const match = u.pathname.match(/^\/@[^\/\?\#]+/);
    return match ? `https://www.tiktok.com${match[0]}` : url;
  } catch {
    return url;
  }
};
