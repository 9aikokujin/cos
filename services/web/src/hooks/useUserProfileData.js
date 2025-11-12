import { useEffect, useState } from "react";

import API from "@/app/api";
import { socialNetworks } from "@/shared/utils/utils";

// export const useUserProfileData = (userId, setValue) => {
//   const [initialData, setInitialData] = useState(null);
//   const [socials, setSocials] = useState([]);
//   const [loading, setLoading] = useState(true);

//   useEffect(() => {
//     const fetchData = async () => {
//       try {
//         const [userRes, accountsRes] = await Promise.all([
//           API.user.getUserById(userId),
//           API.account.getAccounts({ user_id: userId }),
//         ]);

//         // Собираем ФИО
//         const fullName = [userRes.last_name, userRes.first_name, userRes.fullname]
//           .filter(Boolean)
//           .join(" ");

//         setValue("fullName", fullName);
//         setValue("tgId", userRes.tg_id || "");
//         setInitialData({ ...userRes, fullName });

//         // Соцсети
//         const socialsData = accountsRes.channels;
//         setSocials(socialsData);

//         socialsData.forEach((acc) => {
//           const networkName = socialNetworks.find(
//             (n) => n.toLowerCase() === acc.type.toLowerCase()
//           );
//           if (networkName) setValue(networkName, acc.link);
//         });
//       } catch (err) {
//         console.error("Ошибка при загрузке профиля:", err);
//       } finally {
//         setLoading(false);
//       }
//     };

//     fetchData();
//   }, [userId, setValue]);

//   return { initialData, socials, loading };
// };

export const useUserProfileData = (userId, setValue, reset) => {
  const [initialData, setInitialData] = useState(null);
  const [socials, setSocials] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [userRes, accountsRes] = await Promise.all([
          API.user.getUserById(userId),
          API.account.getAccounts({ user_id: userId }),
        ]);

        const fullName = [userRes.last_name, userRes.first_name, userRes.fullname]
          .filter(Boolean)
          .join(" ");

        const socialsData = accountsRes.channels.map((acc) => ({
          id: acc.id,
          type: acc.type,
          link: acc.link,
        }));

        setSocials(socialsData);

        reset({
          fullName,
          tgId: userRes.tg_id || "",
          socials: socialsData.length
            ? socialsData.map((acc) => ({ type: acc.type, link: acc.link }))
            : [],
        });

        setInitialData({ ...userRes, fullName });
      } catch (err) {
        console.error("Ошибка при загрузке профиля:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [userId, reset]);

  return { initialData, socials, loading };
};
