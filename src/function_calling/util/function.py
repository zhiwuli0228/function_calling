class FunctionTool:

    @staticmethod
    def get_current_temperature(location: str, unit: str = "celsius"):
        """Get current temperature at a location.

        Args:
            location: The location to get the temperature for, in the format "City, State, Country".
            unit: The unit to return the temperature in. Defaults to "celsius". (choices: ["celsius", "fahrenheit"])

        Returns:
            the temperature, the location, and the unit in a dict
        """
        return {
            "temperature": 26.1,
            "location": location,
            "unit": unit,
        }

    @staticmethod
    def get_temperature_date(location: str, date: str, unit: str = "celsius"):
        """Get temperature at a location and date.

        Args:
            location: The location to get the temperature for, in the format "City, State, Country".
            date: The date to get the temperature for, in the format "Year-Month-Day".
            unit: The unit to return the temperature in. Defaults to "celsius". (choices: ["celsius", "fahrenheit"])

        Returns:
            the temperature, the location, the date and the unit in a dict
        """
        return {
            "temperature": 25.9,
            "location": location,
            "date": date,
            "unit": unit,
        }

    @staticmethod
    def get_function_by_name(name):
        functions = {
            "get_current_temperature": FunctionTool.get_current_temperature,
            "get_temperature_date": FunctionTool.get_temperature_date,
        }
        if name not in functions:
            raise ValueError(f"Function '{name}' not found.")
        return functions[name]
