import { useState, useEffect, useRef } from "react";
import { useFiltersModalStore } from "@/app/store/filterModal/store";

export const useMultiSelectFilter = (
  applyLabel = "Применить",
  onApply,
  multiple = false,
  resetFilter
) => {
  const setFooter = useFiltersModalStore((s) => s.setFooter);
  const close = useFiltersModalStore((s) => s.close);

  const [selected, setSelected] = useState([]);
  const selectedRef = useRef(selected);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  const toggleSelect = (id) => {
    setSelected((prev) => {
      if (multiple) {
        // мультивыбор
        return prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id];
      } else {
        // одиночный выбор
        return prev.includes(id) ? [] : [id];
      }
    });
  };

  const handleApply = () => {
    const current = selectedRef.current;
    if (onApply) onApply(current);
    close();
  };

  useEffect(() => {
    setFooter({
      text: applyLabel,
      visible: true,
      onClick: handleApply,
      resetFilter: resetFilter,
    });
  }, []);

  return { selected, toggleSelect, setSelected };
};
