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
      default:
        return true;
    }

    return true;
  };