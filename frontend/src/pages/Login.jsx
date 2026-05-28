import React, { useState } from "react";
import { useAuth } from "@/components/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Building2, Loader2, Eye, EyeOff } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

const loginSchema = z.object({
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(1, { message: "Password is required" }),
});

const registerSchema = z.object({
  name: z.string().min(2, { message: "Name must be at least 2 characters" }),
  firmName: z.string().min(2, { message: "Firm name must be at least 2 characters" }),
  email: z.string().email({ message: "Invalid email address" }),
  password: z.string().min(8, { message: "Password must be at least 8 characters" }),
});

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const { login, register: registerUser } = useAuth();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setError,
  } = useForm({
    resolver: zodResolver(isLogin ? loginSchema : registerSchema),
    mode: "onTouched",
  });

  const onSubmit = async (data) => {
    try {
      if (isLogin) {
        await login({ email: data.email, password: data.password });
        toast.success("Logged in successfully");
      } else {
        await registerUser({
          email: data.email,
          password: data.password,
          name: data.name,
          firm_name: data.firmName,
        });
        toast.success("Account created successfully");
      }
      navigate("/");
    } catch (err) {
      if (err.response?.status === 422 && err.response?.data?.detail) {
        // Handle FastAPI validation errors mapping
        const details = err.response.data.detail;
        if (Array.isArray(details)) {
          details.forEach((d) => {
            if (d.loc && d.loc.length > 1) {
              const field = d.loc[d.loc.length - 1];
              setError(field === "firm_name" ? "firmName" : field, { type: "server", message: d.msg });
            }
          });
          return;
        }
      }
      toast.error(err.response?.data?.detail || err.message || "An error occurred");
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    reset();
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 animate-fade-in">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <div className="h-12 w-12 bg-navy-600 rounded-xl flex items-center justify-center shadow-lg">
            <Building2 className="h-6 w-6 text-white" />
          </div>
        </div>
        <h2 className="mt-6 text-center text-3xl font-extrabold text-slate-900 font-heading">
          {isLogin ? "Sign in to TaxPilot" : "Create your firm account"}
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-xl shadow-slate-200/50 sm:rounded-2xl sm:px-10 border border-slate-100">
          <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
            {!isLogin && (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name</label>
                  <input
                    {...register("name")}
                    type="text"
                    className={`appearance-none block w-full px-3 py-2 border rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition sm:text-sm ${
                      errors.name ? "border-red-300 focus:border-red-500" : "border-slate-300 focus:border-navy-600"
                    }`}
                  />
                  {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Firm Name</label>
                  <input
                    {...register("firmName")}
                    type="text"
                    className={`appearance-none block w-full px-3 py-2 border rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition sm:text-sm ${
                      errors.firmName ? "border-red-300 focus:border-red-500" : "border-slate-300 focus:border-navy-600"
                    }`}
                  />
                  {errors.firmName && <p className="mt-1 text-xs text-red-600">{errors.firmName.message}</p>}
                </div>
              </>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email address</label>
              <input
                {...register("email")}
                type="email"
                className={`appearance-none block w-full px-3 py-2 border rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition sm:text-sm ${
                  errors.email ? "border-red-300 focus:border-red-500" : "border-slate-300 focus:border-navy-600"
                }`}
              />
              {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <div className="relative">
                <input
                  {...register("password")}
                  type={showPassword ? "text" : "password"}
                  className={`appearance-none block w-full px-3 py-2 pr-10 border rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition sm:text-sm ${
                    errors.password ? "border-red-300 focus:border-red-500" : "border-slate-300 focus:border-navy-600"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
            </div>

            {isLogin && (
              <div className="flex justify-end -mt-2 mb-2">
                <button type="button" onClick={() => toast.info("Password reset is coming soon. Contact your admin for now.")} className="text-xs text-navy-600 hover:text-navy-800 font-medium hover:underline">
                  Forgot password?
                </button>
              </div>
            )}

            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-navy-600 hover:bg-navy-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy-600 transition disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {isSubmitting ? "Please wait..." : isLogin ? "Sign in" : "Create account"}
              </button>
            </div>
          </form>

          <div className="mt-8">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-slate-500 font-medium">
                  {isLogin ? "New to TaxPilot?" : "Already have an account?"}
                </span>
              </div>
            </div>

            <div className="mt-6">
              <button
                onClick={toggleMode}
                className="w-full flex justify-center py-2.5 px-4 border border-slate-300 rounded-md shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy-600 transition"
              >
                {isLogin ? "Create an account" : "Sign in instead"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
