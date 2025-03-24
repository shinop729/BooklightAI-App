import { useState, InputHTMLAttributes, forwardRef } from 'react';

export interface FormInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  helperText?: string;
  fullWidth?: boolean;
}

const FormInput = forwardRef<HTMLInputElement, FormInputProps>(
  ({ label, error, helperText, fullWidth = true, className = '', ...props }, ref) => {
    const [isFocused, setIsFocused] = useState(false);
    
    const baseClasses = "bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 px-4 py-2";
    const widthClasses = fullWidth ? "w-full" : "";
    const stateClasses = error 
      ? "border border-red-500 focus:ring-red-500" 
      : "focus:ring-blue-500";
    const focusClasses = isFocused ? "ring-2 ring-blue-500" : "";
    
    return (
      <div className={`mb-4 ${fullWidth ? 'w-full' : ''}`}>
        <label className="block text-gray-300 mb-1">
          {label}
        </label>
        
        <input
          ref={ref}
          className={`${baseClasses} ${widthClasses} ${stateClasses} ${focusClasses} ${className}`}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />
        
        {error ? (
          <p className="mt-1 text-red-500 text-sm">{error}</p>
        ) : helperText ? (
          <p className="mt-1 text-gray-400 text-sm">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

FormInput.displayName = 'FormInput';

export default FormInput;
