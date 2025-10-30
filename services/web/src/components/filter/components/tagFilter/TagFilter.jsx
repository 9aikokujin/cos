import { useFilterStore } from "@/app/store/filter/store";

import { useMultiSelectFilter } from "@/hooks/useMultiSelectFilter";
import { hasTags } from "@/shared/utils/filters";

const TagFilter = () => {
  const setTags = useFilterStore((s) => s.setFilterTag);
  const filteredTags = useFilterStore((s) => s.tag);

  const { selected, toggleSelect } = useMultiSelectFilter(
    "Применить",
    (tags) => {
      setTags(tags.join(","));
    },
    true,
    () => setTags(""),
    filteredTags
  );

  return (
    <div className="tag_filter _flex_col_center" style={{ gap: 10 }}>
      <h2>Теги</h2>
      {hasTags.map((tag, index) => (
        <div
          key={index}
          onClick={() => toggleSelect(tag.id)}
          className={`filter_item _flex_center ${selected.includes(tag.id) ? "_active" : ""}`}
        >
          {tag.title}
        </div>
      ))}
    </div>
  );
};

export default TagFilter;
