import { useFiltersModalStore } from "@/app/store/filterModal/store";
import { usePageFilters } from "@/hooks/usePageFilters";

import { Button } from "@/shared/ui/button/Button";

import "./Filter.css";

const Filter = () => {
  const { open } = useFiltersModalStore();
  const filters = usePageFilters();

  const openFilters = () => {
    open(filters, (values) => {
    });
  };
  return (
    <>
      <Button onClick={openFilters} className={"_orange filter_btn"}>
        Фильтры
      </Button>
    </>
  );
};

export default Filter;
