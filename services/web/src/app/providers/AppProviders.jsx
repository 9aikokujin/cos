import { AuthProvider } from "./authProvider/AuthProvider";

export const AppProviders = ({ children }) => {
  return <AuthProvider>{children}</AuthProvider>;
};
