import { useMultiSelectFilter } from "@/hooks/useMultiSelectFilter";
import { hasTags } from "@/shared/utils/filters";

const TagFilter = () => {
  const { selected, toggleSelect } = useMultiSelectFilter("Применить", (tags) => {
    console.log("Выбранные теги:", tags);
  });

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
