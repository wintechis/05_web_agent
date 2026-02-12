from agent import vanilla_web_agent


task =  "Can you use the following api to find all organizations: https://ldpp-extern.iis.fraunhofer.de/virtual/fuseki/query-service-specification.html",

task = "Schalte die Lampe im Raum <http://127.0.0.1:8080/Room_SOR42_G_15> an."
task = "Find the current status of the lamp in the room <http://127.0.0.1:8080/Room_SOR42_G_15>. Return your answers as triples."
result = vanilla_web_agent.run(task)
