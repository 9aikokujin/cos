import API from "@/app/api";
import { socialNetworks } from "@/shared/utils/utils";
import { validateSocialUrl } from "@/shared/utils/validate";

export const useUserProfileSubmit = (
  user,
  userId,
  initialData,
  socials,
  goBack,
  setError,
  showNotification
) => {
  return async (data) => {
    const updates = [];

    // --- Проверка изменений ФИО и Telegram ID ---
    const fullNameChanged = data.fullName.trim() !== initialData.fullName.trim();
    const tgChanged = user.role === "admin" && data.tgId !== (initialData.tg_id || "");

    if (fullNameChanged || tgChanged) {
      const [lastName, firstName, ...rest] = data.fullName.split(" ");
      const fullname = rest.join(" ");

      if (!data.fullName) {
        setError("fullName", { message: "Заполните поле ФИО" });
        return;
      }

      if (!data.tgId) {
        setError("tgId", { message: "Заполните поле Телеграм ID" });
        return;
      }
      updates.push(
        API.user.updateUser(userId, {
          tg_id: user.role === "admin" ? data.tgId : undefined,
          last_name: lastName,
          first_name: firstName,
          fullname,
        })
      );
    }

    // --- Проверка изменений соцсетей ---
    for (const network of socialNetworks) {
      const fieldValue = data[network]?.trim() || "";
      const existing = socials.find((s) => s.type.toLowerCase() === network.toLowerCase());

      if (existing) {
        if (!fieldValue && existing.link) {
          updates.push(API.account.deleteAccount(existing.id)); // удаление
        } else if (fieldValue && fieldValue !== existing.link) {
          const result = validateSocialUrl(fieldValue, network.toLowerCase());
          if (result !== true) {
            setError("socials", { message: result });
            return;
          }

          let cleanValue = fieldValue;
          if (network.toLowerCase() === "tiktok") {
            cleanValue = sanitizeTikTokUrl(cleanValue);
          }

          updates.push(API.account.deleteAccount(existing.id));
          updates.push(
            API.account.createAccount(
              {
                type: network.toLowerCase(),
                link: cleanValue,
                start_views: 0,
                start_likes: 0,
                start_comments: 0,
              },
              userId
            )
          );
        }
      } else if (fieldValue) {
        const result = validateSocialUrl(fieldValue, network.toLowerCase());
        if (result !== true) {
          setError("socials", { message: result });
          return;
        }

        let cleanValue = fieldValue;
        if (network.toLowerCase() === "tiktok") {
          cleanValue = sanitizeTikTokUrl(cleanValue);
        }

        updates.push(
          API.account.createAccount(
            {
              type: network.toLowerCase(),
              link: cleanValue,
              start_views: 0,
              start_likes: 0,
              start_comments: 0,
            },
            userId
          )
        ); // создание
      }
    }

    if (updates.length > 0) {
      await Promise.all(updates);
      showNotification("Профиль обновлен");
    } else {
      console.log("Нет изменений");
    }

    goBack();
  };
};
