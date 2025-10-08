import { useEffect } from "react";
import { useLocation, useParams } from "react-router-dom";

import PageHeader from "@/components/pageHeader/PageHeader";
import Diagram from "@/components/diagram/Diagram";
import Statistic from "@/components/statistic/Statistic";

import { useStatisticData } from "@/hooks/useStatisticData";
import { useFilter } from "@/store/FilterAnalitic/main";

const DiagramPage = () => {
  const { id } = useParams();



  const {
    actions: { resetFilter },
  } = useFilter();

  useEffect(() => {
    return () => {
      if (!window.location.pathname.includes("/diagram")) {
        console.log("обнуление");
        resetFilter();
      }
    };
  }, [resetFilter]);

  const { viewsArray, date } = useStatisticData(id ? id : null);
  return (
    <>
      <PageHeader isShowBtns={false} isFilter />
      <div className="diagram__wrap" style={{ overflowY: "auto" }}>
        <Statistic views={viewsArray} />
        <Diagram views={viewsArray} date={date} />
      </div>
    </>
  );
};

export default DiagramPage;
