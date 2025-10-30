import { useFilterStore } from "@/app/store/filter/store";
import { useMultiSelectFilter } from "@/hooks/useMultiSelectFilter";

import Checkbox from "@/shared/ui/checkbox/Checkbox";
import { SOCIALS } from "@/shared/utils/socialIcon";

const SocialFilter = () => {
  const setSocial = useFilterStore((s) => s.setFilterChannelType);
  const filteredSocials = useFilterStore((s) => s.filter.channel_type);

  const { selected, toggleSelect } = useMultiSelectFilter(
    "Применить",
    (social) => {
      setSocial(social.join("").toUpperCase());
    },
    false,
    () => setSocial(""),
    filteredSocials.toLowerCase()
  );
  return (
    <div className="social_filter _flex_col_center">
      <h2>Выберите соц. сеть</h2>
      <ul className="social_list_icon _flex_sb">
        {SOCIALS.map((social) => (
          <li key={social.id} className="social_item">
            <div className={`social_icon ${social.id === "tiktok" ? "_tiktok" : ""}`}>
              <img src={social.icon} alt={social.label} />
            </div>
            <Checkbox
              label={social.label}
              checked={selected.includes(social.id)}
              onChange={() => toggleSelect(social.id)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
};

export default SocialFilter;
