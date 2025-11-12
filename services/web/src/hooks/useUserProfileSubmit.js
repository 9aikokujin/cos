// import API from "@/app/api";
// import { socialNetworks } from "@/shared/utils/utils";
// import { validateSocialUrl } from "@/shared/utils/validate";

// export const useUserProfileSubmit = (
//   user,
//   userId,
//   initialData,
//   socials,
//   goBack,
//   setError,
//   showNotification
// ) => {
//   return async (data) => {
//     const updates = [];

//     // --- Проверка изменений ФИО и Telegram ID ---
//     const fullNameChanged = data.fullName.trim() !== initialData.fullName.trim();
//     const tgChanged = user.role === "admin" && data.tgId !== (initialData.tg_id || "");

//     if (fullNameChanged || tgChanged) {
//       const [lastName, firstName, ...rest] = data.fullName.split(" ");
//       const fullname = rest.join(" ");

//       if (!data.fullName) {
//         setError("fullName", { message: "Заполните поле ФИО" });
//         return;
//       }

//       if (!data.tgId) {
//         setError("tgId", { message: "Заполните поле Телеграм ID" });
//         return;
//       }
//       updates.push(
//         API.user.updateUser(userId, {
//           tg_id: user.role === "admin" ? data.tgId : undefined,
//           last_name: lastName,
//           first_name: firstName,
//           fullname,
//         })
//       );
//     }

//     // --- Проверка изменений соцсетей ---
//     for (const network of socialNetworks) {
//       const fieldValue = data[network]?.trim() || "";
//       const existing = socials.find((s) => s.type.toLowerCase() === network.toLowerCase());

//       if (existing) {
//         if (!fieldValue && existing.link) {
//           updates.push(API.account.deleteAccount(existing.id)); // удаление
//         } else if (fieldValue && fieldValue !== existing.link) {
//           const result = validateSocialUrl(fieldValue, network.toLowerCase());
//           if (result !== true) {
//             setError("socials", { message: result });
//             return;
//           }

//           let cleanValue = fieldValue;
//           if (network.toLowerCase() === "tiktok") {
//             cleanValue = sanitizeTikTokUrl(cleanValue);
//           }

//           updates.push(API.account.deleteAccount(existing.id));
//           updates.push(
//             API.account.createAccount(
//               {
//                 type: network.toLowerCase(),
//                 link: cleanValue,
//                 start_views: 0,
//                 start_likes: 0,
//                 start_comments: 0,
//               },
//               userId
//             )
//           );
//         }
//       } else if (fieldValue) {
//         const result = validateSocialUrl(fieldValue, network.toLowerCase());
//         if (result !== true) {
//           setError("socials", { message: result });
//           return;
//         }

//         let cleanValue = fieldValue;
//         if (network.toLowerCase() === "tiktok") {
//           cleanValue = sanitizeTikTokUrl(cleanValue);
//         }

//         updates.push(
//           API.account.createAccount(
//             {
//               type: network.toLowerCase(),
//               link: cleanValue,
//               start_views: 0,
//               start_likes: 0,
//               start_comments: 0,
//             },
//             userId
//           )
//         ); // создание
//       }
//     }

//     if (updates.length > 0) {
//       await Promise.all(updates);
//       showNotification("Профиль обновлен");
//     } else {
//       console.log("Нет изменений");
//     }

//     goBack();
//   };
// };

import API from "@/app/api";
import { validateSocialUrl } from "@/shared/utils/validate";

// Опционально: если есть функция для очистки TikTok URL
const sanitizeTikTokUrl = (url) => url.trim();

export const useUserProfileSubmit = (
  user,
  userId,
  initialData,
  socials, // текущее состояние с бэка
  goBack,
  setError,
  showNotification
) => {
  return async (data) => {
    const updates = [];

    // --- Проверка изменений ФИО и Telegram ID ---
    const fullNameChanged = data.fullName.trim() !== initialData.fullName.trim();
    const tgChanged =
      user.role === "admin" && data.tgId !== (initialData.tg_id || "");

    if (fullNameChanged || tgChanged) {
      const [lastName, firstName, ...rest] = data.fullName.split(" ");
      const fullname = rest.join(" ");

      if (!data.fullName.trim()) {
        setError("fullName", { message: "Заполните поле ФИО" });
        return;
      }

      if (user.role === "admin" && !data.tgId.trim()) {
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

    // --- Проверка и обработка соцсетей ---
    // data.socials = [{ type: "instagram", link: "..." }, ...]
    const submittedSocials = data.socials.filter((s) => s.link?.trim() !== "");
    const submittedTypes = submittedSocials.map((s) => s.type.toLowerCase());

    // 1️⃣ Удаляем аккаунты, которых нет в новых данных
    for (const existing of socials) {
      const stillExists = submittedSocials.find(
        (s) =>
          s.type.toLowerCase() === existing.type.toLowerCase() &&
          s.link.trim() === existing.link.trim()
      );

      // если пользователь удалил ссылку или аккаунт отсутствует
      const userDeletedType = !submittedTypes.includes(existing.type.toLowerCase());
      if (!stillExists || userDeletedType) {
        updates.push(API.account.deleteAccount(existing.id));
      }
    }

    // 2️⃣ Добавляем или обновляем аккаунты
    for (const social of submittedSocials) {
      const { type, link } = social;
      const network = type.toLowerCase();
      const value = link.trim();

      if (!value) continue;

      // Проверка валидности
      const result = validateSocialUrl(value, network);
      if (result !== true) {
        setError("socials", { message: result });
        return;
      }

      let cleanValue = value;
      if (network === "tiktok") cleanValue = sanitizeTikTokUrl(cleanValue);

      // Есть ли уже такой аккаунт
      const existing = socials.find(
        (s) =>
          s.type.toLowerCase() === network &&
          s.link.trim() === cleanValue.trim()
      );

      if (!existing) {
        updates.push(
          API.account.createAccount(
            {
              type: network,
              link: cleanValue,
              start_views: 0,
              start_likes: 0,
              start_comments: 0,
            },
            userId
          )
        );
      }
    }

    // --- Отправка всех изменений ---
    if (updates.length > 0) {
      try {
        await Promise.all(updates);
        showNotification("Профиль обновлен");
      } catch (err) {
        console.error("Ошибка при обновлении профиля:", err);
        showNotification("Ошибка при сохранении");
      }
    } else {
      console.log("Нет изменений");
    }

    goBack();
  };
};
