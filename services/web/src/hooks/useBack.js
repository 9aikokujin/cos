import { useNavigate, useLocation } from "react-router-dom";

export const useBack = (fallback = "/") => {
  const navigate = useNavigate();
  const location = useLocation();

  const goBack = () => {
    const from = location.state?.from;

    if (from) {
      navigate(from);
    } else {
      navigate(fallback, { replace: true });
    }
  };

  return goBack;
};
